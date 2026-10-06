from __future__ import annotations

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
from polisyos.data_forge.domains.catalog.batch.embedder import (
    build_hnsw_index as build_catalog_hnsw_index,
)
from polisyos.data_forge.kernel.embeddings import (
    _publish_embedding_generation,
    build_embedding_generation,
    build_embedding_index,
    resolve_embedding_generation,
)
from polisyos.data_forge.kernel.io.generation_basis import GenerationIdentity


class _FakeSentenceTransformer:
    instances: ClassVar[list[_FakeSentenceTransformer]] = []

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self.config = {"model_name": model_name, "dimension": 4}
        self.tokenizer = _FakeTokenizer()
        self.calls: list[dict[str, object]] = []
        type(self).instances.append(self)

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": np.asarray([len(self.model_name), 4.0], dtype=np.float32)}

    def modules(self) -> list[_FakeSentenceTransformer]:
        return [self]

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        self.calls.append(
            {
                "texts": tuple(texts),
                "batch_size": batch_size,
                "show_progress_bar": show_progress_bar,
                "normalize_embeddings": normalize_embeddings,
            }
        )
        vectors = []
        for text in texts:
            base = float((len(text) % 7) + 1)
            vector = np.array([base, base + 1, base + 2, base + 3], dtype=np.float64)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.vstack(vectors)


class _FakeTokenizer:
    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, "fixture": 1}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )


def _prepare_embedding_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, abstract VARCHAR)")
        con.execute(
            "INSERT INTO ac_works VALUES (?, ?, ?)",
            ("a-1", "Academic", "a" * 1201),
        )
        con.execute(
            "INSERT INTO ac_works VALUES (?, ?, ?)",
            ("a-2", "Second", "abstract"),
        )

        con.execute(
            "CREATE TABLE ds_datasets ("
            "id VARCHAR, title VARCHAR, description VARCHAR, "
            "keywords VARCHAR[], variables VARCHAR[])"
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?)",
            (
                "d-1",
                "Catalog",
                "d" * 501,
                [f"k{index}" for index in range(22)],
                [f"v{index}" for index in range(22)],
            ),
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?)",
            ("d-2", "Other", "desc", ["k"], ["v"]),
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _prepare_empty_embedding_db(db_path: Path) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, abstract VARCHAR)")
        con.execute(
            "CREATE TABLE ds_datasets ("
            "id VARCHAR, title VARCHAR, description VARCHAR, "
            "keywords VARCHAR[], variables VARCHAR[])"
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def test_empty_prepared_rows_leave_existing_output_pair_unchanged(tmp_path: Path) -> None:
    embeddings_path = tmp_path / "embeddings.npz"
    index_path = tmp_path / "index.hnsw"
    embeddings_path.write_bytes(b"previous embeddings")
    index_path.write_bytes(b"previous index")

    result = build_embedding_index(
        rows=(),
        embeddings_path=embeddings_path,
        index_path=index_path,
        embedding_model="not-loaded",
        embedding_device="cpu",
        embedding_dimension=4,
    )

    assert result == (0, 4)
    assert embeddings_path.read_bytes() == b"previous embeddings"
    assert index_path.read_bytes() == b"previous index"


def test_empty_domain_rows_leave_existing_output_pairs_unchanged(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-embeddings.duckdb"
    _prepare_empty_embedding_db(db_path)
    academic_dir = tmp_path / "academic"
    catalog_dir = tmp_path / "catalog"
    academic_dir.mkdir()
    catalog_dir.mkdir()
    academic_embeddings = academic_dir / "ac_work_embeddings.npz"
    academic_index = academic_dir / "ac_work_index.hnsw"
    catalog_embeddings = catalog_dir / "ds_dataset_embeddings.npz"
    catalog_index = catalog_dir / "ds_dataset_index.hnsw"
    for path, contents in (
        (academic_embeddings, b"previous academic embeddings"),
        (academic_index, b"previous academic index"),
        (catalog_embeddings, b"previous catalog embeddings"),
        (catalog_index, b"previous catalog index"),
    ):
        path.write_bytes(contents)

    assert build_academic_hnsw_index(
        db_path=db_path,
        index_dir=academic_dir,
        embedding_dimension=4,
    ) == (0, 4)
    assert build_catalog_hnsw_index(db_path=db_path, index_dir=catalog_dir) == 0
    assert academic_embeddings.read_bytes() == b"previous academic embeddings"
    assert academic_index.read_bytes() == b"previous academic index"
    assert catalog_embeddings.read_bytes() == b"previous catalog embeddings"
    assert catalog_index.read_bytes() == b"previous catalog index"


def test_domain_profiles_use_shared_real_hnsw_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    import hnswlib

    real_index = hnswlib.Index
    index_records: list[dict[str, object]] = []

    class _RecordingIndex:
        def __init__(self, *, space: str, dim: int) -> None:
            self.record = {"space": space, "dim": dim, "init": None, "labels": None}
            self._index = real_index(space=space, dim=dim)
            index_records.append(self.record)

        def init_index(self, **kwargs: object) -> None:
            self.record["init"] = dict(kwargs)
            self._index.init_index(**kwargs)

        def add_items(self, vectors: np.ndarray, labels: np.ndarray) -> None:
            self.record["labels"] = labels.copy()
            self._index.add_items(vectors, labels)

        def save_index(self, path: str) -> None:
            self._index.save_index(path)

        def load_index(self, path: str, **kwargs: object) -> None:
            self._index.load_index(path, **kwargs)

        def get_current_count(self) -> int:
            return self._index.get_current_count()

        def get_ids_list(self) -> list[int]:
            return self._index.get_ids_list()

        def get_items(self, labels: np.ndarray) -> np.ndarray:
            return self._index.get_items(labels)

    monkeypatch.setattr(hnswlib, "Index", _RecordingIndex)

    from polisyos.data_forge.kernel import embeddings as kernel_embeddings

    pauses: list[float] = []
    monkeypatch.setattr(kernel_embeddings, "pause_between_batches", pauses.append)

    db_path = tmp_path / "embeddings.duckdb"
    _prepare_embedding_db(db_path)
    academic_dir = tmp_path / "academic"
    catalog_dir = tmp_path / "catalog"
    academic_dir.mkdir()
    catalog_dir.mkdir()

    academic_result = build_academic_hnsw_index(
        db_path=db_path,
        index_dir=academic_dir,
        embedding_model="fake-academic",
        embedding_dimension=4,
        embedding_batch_size=1,
        embedding_device="mps",
        thermal_pause_seconds=0.25,
    )
    catalog_result = build_catalog_hnsw_index(
        db_path=db_path,
        index_dir=catalog_dir,
        embedding_model="fake-catalog",
        embedding_batch_size=1,
        embedding_device="cpu",
        thermal_pause_seconds=0.5,
    )

    assert academic_result == (2, 4)
    assert catalog_result == 2
    assert [
        (instance.model_name, instance.device)
        for instance in _FakeSentenceTransformer.instances
    ] == [("fake-academic", "mps"), ("fake-catalog", "cpu")]

    academic_texts = [
        text
        for call in _FakeSentenceTransformer.instances[0].calls
        for text in call["texts"]
    ]
    catalog_texts = [
        text
        for call in _FakeSentenceTransformer.instances[1].calls
        for text in call["texts"]
    ]
    assert academic_texts == [f"Academic. {'a' * 1200}", "Second. abstract"]
    assert catalog_texts == [
        "Catalog "
        + "d" * 500
        + " "
        + " ".join(f"k{index}" for index in range(20))
        + " "
        + " ".join(f"v{index}" for index in range(20)),
        "Other desc k v",
    ]
    assert all(
        call["normalize_embeddings"] is True
        and call["show_progress_bar"] is False
        for instance in _FakeSentenceTransformer.instances
        for call in instance.calls
    )
    assert [
        call["batch_size"] for call in _FakeSentenceTransformer.instances[0].calls
    ] == [1, 1]
    assert [
        call["batch_size"] for call in _FakeSentenceTransformer.instances[1].calls
    ] == [1, 1]
    assert pauses == [0.25, 0.25, 0.5, 0.5]

    for directory, filename, ids in (
        (academic_dir, "ac_work_embeddings.npz", ["a-1", "a-2"]),
        (catalog_dir, "ds_dataset_embeddings.npz", ["d-1", "d-2"]),
    ):
        with np.load(directory / filename, allow_pickle=True) as payload:
            assert payload["ids"].tolist() == ids
            assert payload["vectors"].dtype == np.float32
            assert payload["vectors"].shape == (2, 4)
            assert np.allclose(
                np.linalg.norm(payload["vectors"], axis=1),
                np.ones(2),
                atol=1e-6,
            )

    assert (academic_dir / "ac_work_index.hnsw").exists()
    assert (catalog_dir / "ds_dataset_index.hnsw").exists()
    assert len(index_records) == 4
    assert all(record["space"] == "cosine" for record in index_records)
    assert all(
        record["init"] == {"max_elements": 2, "ef_construction": 200, "M": 16}
        for record in index_records[::2]
    )
    assert all(
        np.array_equal(record["labels"], np.arange(2))
        for record in index_records[::2]
    )
    assert all(record["init"] is None for record in index_records[1::2])


def test_equal_prepared_texts_produce_equal_vectors_and_preserve_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    rows = (("first-id", "same prepared text"), ("second-id", "another text"))

    build_embedding_index(
        rows=rows,
        embeddings_path=first_dir / "embeddings.npz",
        index_path=first_dir / "index.hnsw",
        embedding_model="fake-a",
        embedding_device="cpu",
        embedding_dimension=4,
        embedding_batch_size=2,
    )
    build_embedding_index(
        rows=rows,
        embeddings_path=second_dir / "embeddings.npz",
        index_path=second_dir / "index.hnsw",
        embedding_model="fake-b",
        embedding_device="cpu",
        embedding_dimension=4,
        embedding_batch_size=2,
    )

    with (
        np.load(first_dir / "embeddings.npz", allow_pickle=True) as first,
        np.load(second_dir / "embeddings.npz", allow_pickle=True) as second,
    ):
        assert first["ids"].tolist() == ["first-id", "second-id"]
        assert second["ids"].tolist() == ["first-id", "second-id"]
        np.testing.assert_array_equal(first["vectors"], second["vectors"])

    assert _FakeSentenceTransformer.instances[0].calls[0]["texts"] == (
        "same prepared text",
        "another text",
    )
    assert _FakeSentenceTransformer.instances[1].calls[0]["texts"] == (
        "same prepared text",
        "another text",
    )


def test_invalid_staged_hnsw_vectors_do_not_replace_selected_generation(
    tmp_path: Path,
) -> None:
    import hnswlib

    index_dir = tmp_path / "index"
    build_embedding_generation(
        rows=(),
        index_dir=index_dir,
        embedding_model="unused-empty-model",
        embedding_device="cpu",
        embedding_dimension=2,
    )
    selector_path = index_dir / "embedding_generation.json"
    previous_selector = selector_path.read_bytes()
    previous_generation = resolve_embedding_generation(index_dir)
    assert previous_generation is not None
    assert previous_generation.status == "empty_generation"

    expected_vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    def write_wrong_native_index(staging: Path) -> tuple[int, int]:
        np.savez(
            staging / "embeddings.npz",
            ids=np.asarray(["ds-1", "ds-2"], dtype=object),
            vectors=expected_vectors,
        )
        index = hnswlib.Index(space="cosine", dim=2)
        index.init_index(max_elements=2, ef_construction=200, M=16)
        index.add_items(expected_vectors[::-1].copy(), np.arange(2))
        index.save_index(str(staging / "index.hnsw"))
        return 2, 2

    with pytest.raises(ValueError, match="HNSW index vectors do not match the matrix"):
        _publish_embedding_generation(
            normalized_rows=[("ds-1", "one"), ("ds-2", "two")],
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_device="cpu",
            basis_kind="fixture",
            projection_rule_version="fixture.v1",
            encoder_identity=GenerationIdentity("sha256:" + "1" * 64),
            legacy_embeddings_path=None,
            legacy_index_path=None,
            stage_builder=write_wrong_native_index,
        )

    assert selector_path.read_bytes() == previous_selector
    current_generation = resolve_embedding_generation(index_dir)
    assert current_generation is not None
    assert current_generation.generation_id == previous_generation.generation_id
