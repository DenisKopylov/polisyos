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
from polisyos.data_forge.domains.catalog.batch.embedder import (
    build_hnsw_index as build_catalog_hnsw_index,
)
from polisyos.data_forge.kernel.embeddings import build_embedding_index


class _FakeSentenceTransformer:
    instances: ClassVar[list[_FakeSentenceTransformer]] = []

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self.model_name = model_name
        self.device = device
        self.calls: list[dict[str, object]] = []
        type(self).instances.append(self)

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

        def __getattr__(self, name: str) -> object:
            return getattr(self._index, name)

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
        (instance.model_name, instance.device) for instance in _FakeSentenceTransformer.instances
    ] == [("fake-academic", "mps"), ("fake-catalog", "cpu")]

    academic_texts = [
        text for call in _FakeSentenceTransformer.instances[0].calls for text in call["texts"]
    ]
    catalog_texts = [
        text for call in _FakeSentenceTransformer.instances[1].calls for text in call["texts"]
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
        call["normalize_embeddings"] is True and call["show_progress_bar"] is False
        for instance in _FakeSentenceTransformer.instances
        for call in instance.calls
    )
    assert [call["batch_size"] for call in _FakeSentenceTransformer.instances[0].calls] == [1, 1]
    assert [call["batch_size"] for call in _FakeSentenceTransformer.instances[1].calls] == [1, 1]
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
    build_records = [record for record in index_records if record["init"] is not None]
    assert len(build_records) == 2
    assert all(record["space"] == "cosine" for record in build_records)
    assert all(
        record["init"] == {"max_elements": 2, "ef_construction": 200, "M": 16}
        for record in build_records
    )
    assert all(np.array_equal(record["labels"], np.arange(2)) for record in build_records)


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


@pytest.mark.parametrize("domain", ["academic", "catalog"])
@pytest.mark.parametrize("failure_copy", [1, 2])
def test_selected_generation_survives_postpublication_compatibility_copy_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, domain: str, failure_copy: int
) -> None:
    """A compatibility copy failure cannot leave a newly mixed pair authoritative."""
    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "db.duckdb"
    _prepare_embedding_db(db_path)
    index_dir = tmp_path / domain
    index_dir.mkdir()
    if domain == "academic":
        build = lambda: build_academic_hnsw_index(  # noqa: E731
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_dimension=4,
        )
    else:
        build = lambda: build_catalog_hnsw_index(  # noqa: E731
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_dimension=4,
        )
    build()
    previous = owner.resolve_embedding_generation(index_dir)
    assert previous is not None and previous.selected
    original_copy = owner._atomic_copy_file
    copies = 0
    selected_at_failure = None

    def fail_copy(source: Path, target: Path) -> None:
        nonlocal copies, selected_at_failure
        copies += 1
        if copies == failure_copy:
            selected_at_failure = owner.resolve_embedding_generation(index_dir)
            raise OSError("compatibility copy failed after publication")
        original_copy(source, target)

    monkeypatch.setattr(owner, "_atomic_copy_file", fail_copy)
    with pytest.raises(
        owner.EmbeddingCompatibilityProjectionError,
        match="compatibility copy failed after publication",
    ) as error:
        build()

    assert selected_at_failure is not None
    assert selected_at_failure.generation_id != previous.generation_id
    fresh = owner.resolve_embedding_generation(index_dir)
    assert fresh == selected_at_failure
    assert fresh is not None and fresh.status == "complete"
    assert error.value.generation_id == fresh.generation_id
    assert error.value.target == index_dir / (
        f"{'ac_work' if domain == 'academic' else 'ds_dataset'}_"
        f"{'embeddings.npz' if failure_copy == 1 else 'index.hnsw'}"
    )
    assert fresh.index_path is not None and fresh.index_path.is_file()
    assert fresh.ids == (("a-1", "a-2") if domain == "academic" else ("d-1", "d-2"))
    if domain == "academic":
        from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore

        reader = ScholarKnowledgeStore(db_path, index_dir)
        try:
            reader._load_work_index()
            assert reader._work_ids == list(fresh.ids)
            assert reader._work_index is not None
            assert reader._work_index.get_current_count() == 2
        finally:
            reader.close()
    else:
        from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore

        reader = DatasetCatalogStore(db_path, index_dir)
        try:
            assert reader.has_vector_index()
            assert reader._dataset_ids == list(fresh.ids)
            assert reader._dataset_index.get_current_count() == 2
        finally:
            reader.close()


def test_catalog_search_after_partial_legacy_copy_and_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A mixed flat pair cannot redirect a selected-generation search."""
    from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore
    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "catalog.duckdb"
    index_dir = tmp_path / "index"
    _prepare_embedding_db(db_path)

    def set_dataset(dataset_id: str, title: str, description: str) -> None:
        with duckdb.connect(str(db_path)) as con:
            con.execute("DELETE FROM ds_datasets")
            con.execute(
                "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?)",
                (dataset_id, title, description, [], []),
            )
            con.execute("CHECKPOINT")

    def build() -> int:
        return build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_dimension=4,
            embedding_device="cpu",
        )

    set_dataset("old", "A", "aaaa")
    assert build() == 1
    previous = owner.resolve_embedding_generation(index_dir)
    assert previous is not None and previous.selected and previous.index_path is not None
    with np.load(previous.embeddings_path, allow_pickle=True) as payload:
        old_vector = np.asarray(payload["vectors"][0], dtype=np.float32)
    flat_vectors = index_dir / "ds_dataset_embeddings.npz"
    flat_index = index_dir / "ds_dataset_index.hnsw"
    old_index_bytes = flat_index.read_bytes()
    old_store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert [row.id for row in old_store.search_by_vector(old_vector)] == ["old"]
    finally:
        old_store.close()

    set_dataset("new", "B", "bbbbb")
    original_copy = owner._atomic_copy_file

    def fail_index_copy(source: Path, target: Path) -> None:
        if target == flat_index:
            raise OSError("second compatibility copy failed")
        original_copy(source, target)

    monkeypatch.setattr(owner, "_atomic_copy_file", fail_index_copy)
    with pytest.raises(owner.EmbeddingCompatibilityProjectionError, match="second compatibility"):
        build()

    selected = owner.resolve_embedding_generation(index_dir)
    assert selected is not None and selected.selected and selected.index_path is not None
    assert selected.generation_id != previous.generation_id
    assert selected.ids == ("new",)
    with np.load(selected.embeddings_path, allow_pickle=True) as payload:
        new_vector = np.asarray(payload["vectors"][0], dtype=np.float32)
    assert float(np.dot(old_vector, new_vector)) < 0.99
    assert flat_vectors.read_bytes() == selected.embeddings_path.read_bytes()
    assert flat_index.read_bytes() == old_index_bytes
    store = DatasetCatalogStore(db_path, index_dir)
    try:
        results = store.search_by_vector(new_vector, top_k=1, min_similarity=0.99)
        assert [row.id for row in results] == ["new"]
        assert results[0].similarity == pytest.approx(1.0, abs=1e-5)
    finally:
        store.close()

    monkeypatch.setattr(owner, "_atomic_copy_file", original_copy)
    assert build() == 1
    recovered = owner.resolve_embedding_generation(index_dir)
    assert recovered is not None and recovered.selected and recovered.index_path is not None
    assert flat_vectors.read_bytes() == recovered.embeddings_path.read_bytes()
    assert flat_index.read_bytes() == recovered.index_path.read_bytes()
    store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert [row.id for row in store.search_by_vector(new_vector, min_similarity=0.99)] == [
            "new"
        ]
    finally:
        store.close()


@pytest.mark.parametrize("domain", ["academic", "catalog"])
def test_selector_failure_leaves_old_generation_and_flat_pair_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, domain: str
) -> None:
    """A failed selection cannot publish only part of the next flat projection."""
    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "db.duckdb"
    _prepare_embedding_db(db_path)
    index_dir = tmp_path / domain
    if domain == "academic":
        build = lambda: build_academic_hnsw_index(  # noqa: E731
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_dimension=4,
        )
        prefix = "ac_work"
    else:
        build = lambda: build_catalog_hnsw_index(  # noqa: E731
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fixture-model",
            embedding_dimension=4,
        )
        prefix = "ds_dataset"
    build()
    before = owner.resolve_embedding_generation(index_dir)
    flat_paths = [index_dir / f"{prefix}_embeddings.npz", index_dir / f"{prefix}_index.hnsw"]
    flat_bytes = [path.read_bytes() for path in flat_paths]
    original_write = owner.atomic_write_json

    def fail_selector(path: Path, payload: object) -> Path:
        if path.name == owner.GENERATION_SELECTOR_FILENAME:
            raise OSError("selector unavailable")
        return original_write(path, payload)

    monkeypatch.setattr(owner, "atomic_write_json", fail_selector)
    with pytest.raises(OSError, match="selector unavailable"):
        build()

    assert owner.resolve_embedding_generation(index_dir) == before
    assert [path.read_bytes() for path in flat_paths] == flat_bytes


@pytest.mark.parametrize("domain", ["academic", "catalog"])
def test_native_domain_index_preserves_query_dependent_cosine_ranks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, domain: str
) -> None:
    """Three non-tied vectors distinguish labels and query-independent output."""
    import hnswlib

    from polisyos.data_forge.kernel import embeddings as owner

    # The encoder is a wiring double. DuckDB, float32 storage and HNSW are real;
    # these finite topology expectations make no model-quality/ANN-recall claim.
    vectors_by_title = {
        "x": [1.0, 0.0, 0.0, 0.0],
        "y": [0.0, 1.0, 0.0, 0.0],
        "z": [0.6, 0.8, 0.0, 0.0],
    }

    class _TopologyEncoder(_FakeSentenceTransformer):
        def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
            assert kwargs["normalize_embeddings"] is True
            return np.asarray([vectors_by_title[text[0]] for text in texts], dtype=np.float64)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_TopologyEncoder),
    )
    db_path = tmp_path / "topology.duckdb"
    _prepare_empty_embedding_db(db_path)
    with duckdb.connect(str(db_path)) as con:
        # SQL insertion order deliberately differs from canonical label order.
        for identifier in ("z", "x", "y"):
            con.execute("INSERT INTO ac_works VALUES (?, ?, ?)", (identifier, identifier, "a"))
            con.execute(
                "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?)",
                (identifier, identifier, "a", [], []),
            )
        con.execute("CHECKPOINT")
    index_dir = tmp_path / domain
    build = build_academic_hnsw_index if domain == "academic" else build_catalog_hnsw_index
    result = build(
        db_path=db_path,
        index_dir=index_dir,
        embedding_dimension=99,
        embedding_batch_size=2,
        embedding_device="cpu",
    )
    assert result == ((3, 4) if domain == "academic" else 3)
    generation = owner.resolve_embedding_generation(index_dir)
    assert generation is not None and generation.selected and generation.index_path is not None
    assert generation.ids == ("x", "y", "z")
    assert generation.dimension == 4
    with np.load(generation.embeddings_path, allow_pickle=True) as payload:
        assert payload["ids"].tolist() == ["x", "y", "z"]
        assert payload["vectors"].dtype == np.float32
        np.testing.assert_allclose(payload["vectors"], list(vectors_by_title.values()))
    fresh = hnswlib.Index(space="cosine", dim=4)
    fresh.load_index(str(generation.index_path))
    fresh.set_num_threads(1)
    fresh.set_ef(100)
    assert fresh.M == 16
    assert fresh.ef_construction == 200
    assert set(fresh.get_ids_list()) == {0, 1, 2}
    queries = np.asarray([vectors_by_title["x"], vectors_by_title["y"]], dtype=np.float32)
    labels, distances = fresh.knn_query(queries, k=2)
    # Independent exact cosine values: x·(x,z,y)=(1,.6,0),
    # y·(y,z,x)=(1,.8,0); k=2 < N=3 and neither query has a tie.
    assert labels.tolist() == [[0, 2], [1, 2]]
    np.testing.assert_allclose(distances, [[0.0, 0.4], [0.0, 0.2]], atol=1e-6)


@pytest.mark.parametrize("domain", ["academic", "catalog"])
@pytest.mark.parametrize(
    "fault",
    [
        "vector",
        "labels",
        "float64",
        "nonfinite",
        "unreadable",
        "inventory_fields",
        "inventory_json",
    ],
)
def test_semantic_staging_fault_preserves_useful_selected_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, domain: str, fault: str
) -> None:
    """Coherent inventory hashes cannot select an unreadable native generation."""
    import hnswlib

    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "db.duckdb"
    _prepare_embedding_db(db_path)
    index_dir = tmp_path / domain
    build = build_academic_hnsw_index if domain == "academic" else build_catalog_hnsw_index
    kwargs = {
        "db_path": db_path,
        "index_dir": index_dir,
        "embedding_model": "fixture-model",
        "embedding_dimension": 4,
        "embedding_device": "cpu",
    }
    build(**kwargs)
    before = owner.resolve_embedding_generation(index_dir)
    assert before is not None and before.selected
    selector_bytes = (index_dir / owner.GENERATION_SELECTOR_FILENAME).read_bytes()
    with np.load(before.embeddings_path, allow_pickle=True) as payload:
        query = payload["vectors"][0].copy()
    original_stage = owner._build_embedding_index_with_encoder

    def corrupt_stage(**stage_kwargs: object) -> tuple[int, int]:
        result = original_stage(**stage_kwargs)
        matrix_path = Path(stage_kwargs["embeddings_path"])
        index_path = Path(stage_kwargs["index_path"])
        with np.load(matrix_path, allow_pickle=True) as payload:
            ids = payload["ids"].copy()
            vectors = payload["vectors"].copy()
        if fault in {"float64", "nonfinite"}:
            if fault == "float64":
                vectors = vectors.astype(np.float64)
            else:
                vectors[0, 0] = np.nan
            np.savez(matrix_path, ids=ids, vectors=vectors)
        elif fault == "unreadable":
            index_path.write_bytes(b"not an HNSW index")
        else:
            if fault == "vector":
                vectors[0] = np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            labels = np.arange(len(ids)) + (1 if fault == "labels" else 0)
            corrupted = hnswlib.Index(space="cosine", dim=4)
            corrupted.init_index(max_elements=len(ids), M=16, ef_construction=200)
            corrupted.add_items(vectors, labels)
            corrupted.save_index(str(index_path))
        # The publisher hashes these controlled output bytes after return.
        return result

    if fault.startswith("inventory"):
        original_write = owner.atomic_write_json

        def corrupt_inventory(path: Path, payload: object) -> Path:
            if path.name != "inventory.json":
                return original_write(path, payload)
            if fault == "inventory_json":
                path.write_text("{not valid JSON", encoding="utf-8")
                return path
            assert isinstance(payload, dict)
            return original_write(path, {**payload, "schema_version": "unsupported-inventory"})

        monkeypatch.setattr(owner, "atomic_write_json", corrupt_inventory)
        expected_error = ValueError
    else:
        monkeypatch.setattr(owner, "_build_embedding_index_with_encoder", corrupt_stage)
        expected_error = owner._EmbeddingIndexAdmissionError
    with pytest.raises(expected_error):
        build(**kwargs)
    assert (index_dir / owner.GENERATION_SELECTOR_FILENAME).read_bytes() == selector_bytes
    assert owner.resolve_embedding_generation(index_dir) == before
    index, ids = owner._load_selected_embedding_index(before)
    labels, distances = index.knn_query(query.reshape(1, -1), k=1)
    assert ids[int(labels[0, 0])] == before.ids[0]
    assert distances[0, 0] == pytest.approx(0.0, abs=1e-6)

    if domain == "academic":
        from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore

        reader = ScholarKnowledgeStore(db_path, index_dir)
        try:
            reader._load_work_index()
            assert reader._work_ids == list(before.ids)
            assert reader._work_index is not None
        finally:
            reader.close()
    else:
        from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore

        reader = DatasetCatalogStore(db_path, index_dir)
        try:
            assert reader.has_vector_index()
            assert reader._dataset_ids == list(before.ids)
        finally:
            reader.close()


def test_generation_sorting_preserves_legacy_order_and_id_vector_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only versioned generations canonicalize membership order."""
    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    rows = (("z", "first text"), ("a", "different text"))
    build_embedding_index(
        rows=rows,
        embeddings_path=tmp_path / "legacy.npz",
        index_path=tmp_path / "legacy.hnsw",
        embedding_model="fixture",
        embedding_device="cpu",
    )
    for name, permutation in (("forward", rows), ("reverse", rows[::-1])):
        owner.build_embedding_generation(
            rows=permutation,
            index_dir=tmp_path / name,
            embedding_model="fixture",
            embedding_device="cpu",
        )
    with np.load(tmp_path / "legacy.npz", allow_pickle=True) as legacy:
        assert legacy["ids"].tolist() == ["z", "a"]
        legacy_vectors = dict(zip(legacy["ids"].tolist(), legacy["vectors"], strict=True))
    for name in ("forward", "reverse"):
        generation = owner.resolve_embedding_generation(tmp_path / name)
        assert generation is not None and generation.ids == ("a", "z")
        with np.load(generation.embeddings_path, allow_pickle=True) as payload:
            for identifier, vector in zip(payload["ids"].tolist(), payload["vectors"], strict=True):
                np.testing.assert_array_equal(vector, legacy_vectors[identifier])


@pytest.mark.parametrize("invalid_ids", [("",), ("a", "a"), (1, "1")])
def test_invalid_canonical_membership_cannot_replace_selector(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, invalid_ids: tuple[object, ...]
) -> None:
    from polisyos.data_forge.kernel import embeddings as owner

    _install_fake_sentence_transformer(monkeypatch)
    options = {"index_dir": tmp_path, "embedding_model": "fixture", "embedding_device": "cpu"}
    owner.build_embedding_generation(rows=(("old", "old text"),), **options)
    before = (tmp_path / owner.GENERATION_SELECTOR_FILENAME).read_bytes()
    with pytest.raises(ValueError, match="embedding identifiers must be"):
        owner.build_embedding_generation(
            rows=tuple((identifier, "text") for identifier in invalid_ids), **options
        )
    assert (tmp_path / owner.GENERATION_SELECTOR_FILENAME).read_bytes() == before


@pytest.mark.parametrize("domain", ["academic", "catalog"])
def test_run_embed_manifest_preserves_actual_dimension_device_and_batches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, domain: str
) -> None:
    from polisyos.data_forge.domains.academic.batch import embedder as academic_embedder
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
    from polisyos.data_forge.domains.catalog.batch import embedder as catalog_embedder
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.kernel import embeddings as owner

    class _BoundEncoder(_FakeSentenceTransformer):
        tokenizer = types.SimpleNamespace(get_vocab=lambda: {"policy": 0})

        def state_dict(self) -> dict[str, np.ndarray]:
            return {"encoder.weight": np.asarray([1.0], dtype=np.float32)}

    _BoundEncoder.instances.clear()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_BoundEncoder),
    )
    if domain == "academic":
        config = AcademicBatchConfig(
            snapshot_root=tmp_path,
            embedding_model="fixture-academic",
            embedding_dimension=99,
            embedding_batch_size=2,
            embedding_device="supplied-device",
        )
        run = academic_embedder.run_embed
        expected_device = "supplied-device"
    else:
        config = DatasetBatchConfig(
            snapshot_root=tmp_path,
            embedding_model="fixture-catalog",
            embedding_dimension=99,
            embedding_batch_size=2,
            embedding_device="auto",
        )
        run = catalog_embedder.run_embed
        expected_device = config.resolved_embedding_device
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_embedding_db(config.db_path)
    with duckdb.connect(str(config.db_path)) as con:
        con.execute("INSERT INTO ac_works VALUES ('a-3', 'Third', 'material')")
        con.execute("INSERT INTO ds_datasets VALUES ('d-3', 'Third', 'material', [], [])")
        con.execute("CHECKPOINT")
    pauses: list[float] = []
    monkeypatch.setattr(owner, "pause_between_batches", pauses.append)
    assert run(config, thermal=True) == 3
    assert pauses == [0.5, 0.5]
    instance = _BoundEncoder.instances[-1]
    assert instance.device == expected_device
    assert [call["batch_size"] for call in instance.calls] == [2, 1]
    manifest = json.loads((config.manifests_dir / "embed.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["metrics"]["thermal"] is True
    assert manifest["metrics"]["embedded"] == 3
    metadata = manifest["metrics"]["embedding_generation"]
    assert metadata["embedding_dimension"] == 4
    assert metadata["embedding_model"] == config.embedding_model
    inventory = json.loads(Path(metadata["inventory"]).read_text(encoding="utf-8"))
    assert inventory["embedding_device"] == expected_device
    assert inventory["embedding_dimension"] == 4
    assert any(artifact["path"] == metadata["inventory"] for artifact in manifest["artifacts"])
