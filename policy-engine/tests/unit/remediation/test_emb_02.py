from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.academic.batch.embedder import (
    build_hnsw_index as build_academic_hnsw_index,
)


class _FakeSentenceTransformer:
    instances: ClassVar[list[_FakeSentenceTransformer]] = []

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        type(self).instances.append(self)

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar
        vectors: list[np.ndarray] = []
        for text in texts:
            base = float((len(text) % 7) + 1)
            vector = np.array([base, base + 1, base + 2, base + 3], dtype=np.float64)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.vstack(vectors)


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )


def _prepare_db(path: Path, rows: list[tuple[str, str, str]]) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, abstract VARCHAR)")
        con.executemany("INSERT INTO ac_works VALUES (?, ?, ?)", rows)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _selector(index_dir: Path) -> dict[str, object]:
    return json.loads((index_dir / "embedding_generation.json").read_text(encoding="utf-8"))


def _inventory(index_dir: Path, selector: dict[str, object]) -> dict[str, object]:
    relative = str(selector["inventory"])
    return json.loads((index_dir / relative).read_text(encoding="utf-8"))


def test_nonempty_build_publishes_one_complete_selected_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    _prepare_db(db_path, [("a-2", "Second", "b"), ("a-1", "First", "a")])

    assert build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
        embedding_batch_size=1,
    ) == (2, 4)

    selector = _selector(index_dir)
    assert selector["status"] == "complete"
    inventory = _inventory(index_dir, selector)
    assert inventory["status"] == "complete"
    assert inventory["embedding_model"] == "fake-model@v1"
    assert inventory["ids"] == ["a-1", "a-2"]
    assert set(inventory["files"]) == {"embeddings", "index", "ids", "basis"}
    generation_dir = index_dir / "embedding_generations" / str(selector["generation_id"])
    assert generation_dir.is_dir()
    assert all(
        (generation_dir / str(item["path"])).is_file() for item in inventory["files"].values()
    )
    with np.load(generation_dir / "embeddings.npz", allow_pickle=True) as payload:
        assert payload["ids"].tolist() == ["a-1", "a-2"]
        assert payload["vectors"].shape == (2, 4)


def test_failed_generation_keeps_previous_selection_and_generation_intact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    _prepare_db(db_path, [("a-1", "First", "a")])
    build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    before = _selector(index_dir)
    before_generation = index_dir / "embedding_generations" / str(before["generation_id"])
    before_inventory = (before_generation / "inventory.json").read_bytes()

    import polisyos.data_forge.domains.academic.batch.embedder as embedder

    def fail_after_staging(*args: object, **kwargs: object) -> tuple[int, int]:
        del args, kwargs
        raise RuntimeError("synthetic HNSW failure")

    monkeypatch.setattr(embedder, "build_embedding_index", fail_after_staging)
    with pytest.raises(RuntimeError, match="synthetic HNSW failure"):
        build_academic_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v2",
            embedding_dimension=4,
        )

    assert _selector(index_dir) == before
    assert (before_generation / "inventory.json").read_bytes() == before_inventory


def test_empty_build_selects_typed_empty_generation_without_reusing_old_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    populated_db = tmp_path / "populated.duckdb"
    empty_db = tmp_path / "empty.duckdb"
    index_dir = tmp_path / "academic"
    _prepare_db(populated_db, [("a-1", "First", "a")])
    _prepare_db(empty_db, [])
    build_academic_hnsw_index(
        db_path=populated_db,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    previous = _selector(index_dir)

    assert build_academic_hnsw_index(
        db_path=empty_db,
        index_dir=index_dir,
        embedding_model="fake-model@v2",
        embedding_dimension=4,
    ) == (0, 4)

    selector = _selector(index_dir)
    assert selector["status"] == "empty_generation"
    assert selector["generation_id"] != previous["generation_id"]
    inventory = _inventory(index_dir, selector)
    assert inventory["status"] == "empty_generation"
    assert inventory["ids"] == []
    old_generation = index_dir / "embedding_generations" / str(previous["generation_id"])
    assert old_generation.is_dir()
    assert not (
        index_dir / "embedding_generations" / str(selector["generation_id"]) / "index.hnsw"
    ).exists()


def test_model_revision_selects_new_generation_and_keeps_id_vector_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    _prepare_db(db_path, [("a-2", "Second", "b"), ("a-1", "First", "a")])

    build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    first = _selector(index_dir)
    first_inventory = _inventory(index_dir, first)
    first_dir = index_dir / "embedding_generations" / str(first["generation_id"])
    with np.load(first_dir / "embeddings.npz", allow_pickle=True) as payload:
        first_vectors = dict(zip(payload["ids"].tolist(), payload["vectors"], strict=True))

    build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v2",
        embedding_dimension=4,
    )
    second = _selector(index_dir)
    second_inventory = _inventory(index_dir, second)
    assert second["generation_id"] != first["generation_id"]
    assert second_inventory["embedding_model"] == "fake-model@v2"
    assert first_inventory["basis"]["basis_digest"] != second_inventory["basis"]["basis_digest"]
    second_dir = index_dir / "embedding_generations" / str(second["generation_id"])
    with np.load(second_dir / "embeddings.npz", allow_pickle=True) as payload:
        second_vectors = dict(zip(payload["ids"].tolist(), payload["vectors"], strict=True))
    assert set(first_vectors) == set(second_vectors) == {"a-1", "a-2"}
    for row_id in first_vectors:
        np.testing.assert_array_equal(first_vectors[row_id], second_vectors[row_id])
