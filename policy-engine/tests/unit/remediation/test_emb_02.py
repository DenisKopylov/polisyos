from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.embedder import (
    build_hnsw_index as build_academic_hnsw_index,
)
from polisyos.data_forge.domains.academic.batch.publish import (
    run_publish as run_academic_publish,
)
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.embedder import (
    build_hnsw_index as build_catalog_hnsw_index,
)
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.batch.publish import run_publish
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord, DistributionRecord


class _FakeSentenceTransformer:
    instances: ClassVar[list[_FakeSentenceTransformer]] = []
    encode_calls: ClassVar[int] = 0

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
        type(self).encode_calls += 1
        model_offset = 1.0 if self.model_name.endswith("@v1") else 2.0
        vectors: list[np.ndarray] = []
        for text in texts:
            base = float((len(text) % 7) + model_offset)
            vector = np.array([base, base + 1, base + 2, base + 3], dtype=np.float64)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            vectors.append(vector)
        return np.vstack(vectors)


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
    _FakeSentenceTransformer.encode_calls = 0
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )


def _prepare_db(path: Path, rows: list[tuple[str, str, str]]) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, abstract VARCHAR)")
        if rows:
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
    index_dir.mkdir()
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
    index_dir.mkdir()
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

    import hnswlib

    real_index = hnswlib.Index

    class _FailingIndex:
        def __init__(self, *, space: str, dim: int) -> None:
            self._index = real_index(space=space, dim=dim)

        def init_index(self, **kwargs: object) -> None:
            self._index.init_index(**kwargs)

        def add_items(self, vectors: np.ndarray, labels: np.ndarray) -> None:
            self._index.add_items(vectors, labels)

        def save_index(self, path: str) -> None:
            assert Path(path).with_name("embeddings.npz").is_file()
            raise RuntimeError("synthetic HNSW failure")

    monkeypatch.setattr(hnswlib, "Index", _FailingIndex)
    with pytest.raises(RuntimeError, match="synthetic HNSW failure"):
        build_academic_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v2",
            embedding_dimension=4,
        )

    assert _selector(index_dir) == before
    assert (before_generation / "inventory.json").read_bytes() == before_inventory

    monkeypatch.setattr(hnswlib, "Index", real_index)
    store = ScholarKnowledgeStore(db_path, index_dir)
    try:
        store._load_work_index()
        assert store._work_ids == ["a-1"]
        assert store._work_index is not None
    finally:
        store.close()


def test_empty_build_selects_typed_empty_generation_without_reusing_old_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    populated_db = tmp_path / "populated.duckdb"
    empty_db = tmp_path / "empty.duckdb"
    index_dir = tmp_path / "academic"
    index_dir.mkdir()
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

    store = ScholarKnowledgeStore(empty_db, index_dir)
    try:
        store._load_work_index()
        assert store._work_index is None
        assert store._work_ids is None
    finally:
        store.close()


def test_model_revision_selects_new_generation_and_keeps_id_vector_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    index_dir.mkdir()
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
    assert _FakeSentenceTransformer.encode_calls == 2
    for row_id in first_vectors:
        assert not np.array_equal(first_vectors[row_id], second_vectors[row_id])


def test_row_permutation_preserves_id_vector_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    first_db = tmp_path / "first.duckdb"
    second_db = tmp_path / "second.duckdb"
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    rows = [("a-1", "First", "a"), ("a-2", "Second", "b")]
    _prepare_db(first_db, rows)
    _prepare_db(second_db, list(reversed(rows)))

    build_academic_hnsw_index(
        db_path=first_db,
        index_dir=first_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    build_academic_hnsw_index(
        db_path=second_db,
        index_dir=second_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )

    first_selector = _selector(first_dir)
    second_selector = _selector(second_dir)
    first_generation = first_dir / "embedding_generations" / str(first_selector["generation_id"])
    second_generation = second_dir / "embedding_generations" / str(second_selector["generation_id"])
    with (
        np.load(first_generation / "embeddings.npz", allow_pickle=True) as first,
        np.load(second_generation / "embeddings.npz", allow_pickle=True) as second,
    ):
        first_vectors = dict(zip(first["ids"].tolist(), first["vectors"], strict=True))
        second_vectors = dict(zip(second["ids"].tolist(), second["vectors"], strict=True))
    assert set(first_vectors) == set(second_vectors) == {"a-1", "a-2"}
    for row_id in first_vectors:
        np.testing.assert_array_equal(first_vectors[row_id], second_vectors[row_id])


def test_reader_fails_closed_when_selected_generation_member_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    index_dir.mkdir()
    _prepare_db(db_path, [("a-1", "First", "a")])
    build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    selector = _selector(index_dir)
    generation_dir = index_dir / "embedding_generations" / str(selector["generation_id"])
    (generation_dir / "index.hnsw").unlink()

    store = ScholarKnowledgeStore(db_path, index_dir)
    try:
        store._load_work_index()
        assert store._work_index is None
        assert store._work_ids is None
    finally:
        store.close()


@pytest.mark.parametrize("member_name", ["basis.json", "ids.json"])
def test_reader_fails_closed_when_selected_generation_member_is_tampered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, member_name: str
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "academic.duckdb"
    index_dir = tmp_path / "academic"
    index_dir.mkdir()
    _prepare_db(db_path, [("a-1", "First", "a")])
    build_academic_hnsw_index(
        db_path=db_path,
        index_dir=index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )
    selector = _selector(index_dir)
    generation_dir = index_dir / "embedding_generations" / str(selector["generation_id"])
    (generation_dir / member_name).write_text("{}\n", encoding="utf-8")

    store = ScholarKnowledgeStore(db_path, index_dir)
    try:
        store._load_work_index()
        assert store._work_index is None
        assert store._work_ids is None
    finally:
        store.close()


def _write_catalog_registry(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "sources:",
                "  - name: worldbank",
                "    family: worldbank",
                "    wave: A",
                "    endpoint: https://example.test/worldbank",
                "    enabled: true",
                "    execution_tier: transport_ready",
                "    run_lane: empirical",
                "    publish_blocking: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_catalog_publish_inputs(config: DatasetBatchConfig) -> None:
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"id":"ds-1"}\n', encoding="utf-8")
    config.duplicates_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.duplicates_report_path.write_text("dataset_id,duplicate_id\n", encoding="utf-8")
    config.qc_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.qc_report_path.write_text(
        json.dumps(
            {
                "passed": True,
                "metrics": {
                    "machine_readable_distribution_pct": 100.0,
                    "parser_supported_distribution_pct": 100.0,
                    "datasets_with_metric_binding_pct": 100.0,
                    "datasets_with_schema_profile_pct": 100.0,
                    "transport_ready_var_coverage_pct": 100.0,
                    "execution_readiness_score_avg": 0.9,
                },
            }
        ),
        encoding="utf-8",
    )
    config.benchmark_report_path.write_text(
        json.dumps(
            {
                "evaluation_mode": "full-ready",
                "metrics": {
                    "benchmark_search_top5_relevance_pct": 100.0,
                    "benchmark_retrieval_ready_pct": 100.0,
                    "benchmark_transport_ready_pct": 100.0,
                    "benchmark_foundry_fitness_pct": 100.0,
                    "benchmark_source_preflight_ready_pct": 100.0,
                    "benchmark_bulk_equivalence_mismatch_rate": 0.0,
                    "benchmark_bulk_equivalence_blocking_sources_total": 0,
                },
                "source_preflight": {"sources": [{"source": "worldbank", "status": "complete"}]},
            }
        ),
        encoding="utf-8",
    )


def test_catalog_reader_and_publish_manifest_bind_to_selected_inventory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    registry_path = tmp_path / "registry.yaml"
    _write_catalog_registry(registry_path)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot", registry_path=registry_path)
    config.index_dir.mkdir(parents=True, exist_ok=True)
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-1",
                    title="Dataset",
                    description="Description",
                    source="worldbank",
                    dataset_id="ds-1",
                    source_dataset_id="ds-1",
                    execution_tier="transport_ready",
                    distributions=[
                        DistributionRecord(
                            id="dist-1",
                            connector_type="worldbank.wdi",
                            source_locator="ds-1",
                            parser_supported=True,
                            machine_readable=True,
                        )
                    ],
                )
            ]
        ),
        db_path=config.db_path,
    )
    assert (
        build_catalog_hnsw_index(
            db_path=config.db_path,
            index_dir=config.index_dir,
            embedding_model="fake-model@v1",
            embedding_batch_size=1,
            embedding_device="cpu",
        )
        == 1
    )
    store = DatasetCatalogStore(config.db_path, config.index_dir)
    try:
        assert store.has_vector_index() is True
        selector = _selector(config.index_dir)
        generation_dir = config.index_dir / "embedding_generations" / str(selector["generation_id"])
        with np.load(generation_dir / "embeddings.npz", allow_pickle=True) as payload:
            query_vector = np.asarray(payload["vectors"][0], dtype=np.float32)
        results = store.search_by_vector(query_vector, top_k=1, min_similarity=0.0)
        assert [result.id for result in results] == ["ds-1"]
    finally:
        store.close()

    _write_catalog_publish_inputs(config)
    manifest_path = run_publish(config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selector = _selector(config.index_dir)
    generation_id = str(selector["generation_id"])
    assert manifest["extra"]["embedding_generation"]["generation_id"] == generation_id
    assert any(
        f"embedding_generations/{generation_id}/inventory.json" in item["path"]
        for item in manifest["artifacts"]
    )


def test_catalog_empty_generation_reader_does_not_reuse_legacy_files(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "catalog.duckdb"
    index_dir = tmp_path / "catalog"
    index_dir.mkdir()
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE ds_datasets ("
            "id VARCHAR, title VARCHAR, description VARCHAR, "
            "keywords VARCHAR[], variables VARCHAR[])"
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    assert (
        build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
        )
        == 0
    )

    store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert store.has_vector_index() is False
        assert store.search_by_vector(np.ones(4, dtype=np.float32)) == []
    finally:
        store.close()


def test_academic_publish_manifest_binds_to_selected_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    config.index_dir.mkdir(parents=True, exist_ok=True)
    _prepare_db(config.db_path, [("a-1", "First", "a")])
    build_academic_hnsw_index(
        db_path=config.db_path,
        index_dir=config.index_dir,
        embedding_model="fake-model@v1",
        embedding_dimension=4,
    )

    manifest_path = run_academic_publish(config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selector = _selector(config.index_dir)
    generation_id = str(selector["generation_id"])
    assert manifest["extra"]["embedding_generation"]["generation_id"] == generation_id
    assert any(
        f"embedding_generations/{generation_id}/inventory.json" in item["path"]
        for item in manifest["artifacts"]
    )


def test_catalog_copy_failure_keeps_one_readable_generation_and_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed legacy copy must not make readers combine two generations."""
    _install_fake_sentence_transformer(monkeypatch)
    from polisyos.data_forge.kernel import embeddings as kernel_embeddings

    db_path = tmp_path / "catalog.duckdb"
    index_dir = tmp_path / "catalog"
    index_dir.mkdir()
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-1",
                    title="Dataset",
                    description="Description",
                    source="worldbank",
                    dataset_id="ds-1",
                    source_dataset_id="ds-1",
                    execution_tier="transport_ready",
                    distributions=[
                        DistributionRecord(
                            id="dist-1",
                            connector_type="worldbank.wdi",
                            source_locator="ds-1",
                            parser_supported=True,
                            machine_readable=True,
                        )
                    ],
                )
            ]
        ),
        db_path=db_path,
    )

    legacy_embeddings = index_dir / "ds_dataset_embeddings.npz"
    legacy_index = index_dir / "ds_dataset_index.hnsw"
    previous_vectors = np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    np.savez(legacy_embeddings, ids=np.array(["old-id"], dtype=object), vectors=previous_vectors)
    import hnswlib

    previous_index = hnswlib.Index(space="cosine", dim=4)
    previous_index.init_index(max_elements=1, ef_construction=200, M=16)
    previous_index.add_items(previous_vectors, np.array([0]))
    previous_index.save_index(str(legacy_index))
    previous_index_bytes = legacy_index.read_bytes()

    previous = kernel_embeddings.resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings,
        legacy_index_path=legacy_index,
    )
    assert previous is not None
    assert previous.status == "legacy"
    assert previous.ids == ("old-id",)

    assert (
        build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v1",
            embedding_device="cpu",
        )
        == 1
    )
    selected_previous = kernel_embeddings.resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings,
        legacy_index_path=legacy_index,
    )
    assert selected_previous is not None
    assert selected_previous.selected is True
    assert selected_previous.status == "complete"
    previous_selector = (index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME).read_bytes()
    previous_index_bytes = legacy_index.read_bytes()

    import hnswlib

    real_index = hnswlib.Index

    class _FailingIndex:
        def __init__(self, *, space: str, dim: int) -> None:
            self._index = real_index(space=space, dim=dim)

        def init_index(self, **kwargs: object) -> None:
            self._index.init_index(**kwargs)

        def add_items(self, vectors: np.ndarray, labels: np.ndarray) -> None:
            self._index.add_items(vectors, labels)

        def save_index(self, path: str) -> None:
            assert Path(path).with_name("embeddings.npz").is_file()
            raise RuntimeError("synthetic catalog HNSW publication failure")

    monkeypatch.setattr(hnswlib, "Index", _FailingIndex)
    with pytest.raises(RuntimeError, match="catalog HNSW publication failure"):
        build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v2",
            embedding_device="cpu",
        )
    monkeypatch.setattr(hnswlib, "Index", real_index)
    assert (index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME).read_bytes() == (
        previous_selector
    )
    after_early_failure = kernel_embeddings.resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings,
        legacy_index_path=legacy_index,
    )
    assert after_early_failure is not None
    assert after_early_failure.generation_id == selected_previous.generation_id
    assert legacy_index.read_bytes() == previous_index_bytes
    old_store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert old_store.has_vector_index() is True
        with np.load(selected_previous.embeddings_path, allow_pickle=True) as payload:
            old_query_vector = np.asarray(payload["vectors"][0], dtype=np.float32)
        old_results = old_store.search_by_vector(old_query_vector, top_k=1, min_similarity=0.0)
        assert [result.id for result in old_results] == ["ds-1"]
        assert old_results[0].similarity == pytest.approx(1.0, abs=1e-5)
    finally:
        old_store.close()

    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="ds-2",
                    title="New",
                    description="XYZ",
                    source="worldbank",
                    dataset_id="ds-2",
                    source_dataset_id="ds-2",
                    execution_tier="transport_ready",
                    distributions=[
                        DistributionRecord(
                            id="dist-2",
                            connector_type="worldbank.wdi",
                            source_locator="ds-2",
                            parser_supported=True,
                            machine_readable=True,
                        )
                    ],
                )
            ]
        ),
        db_path=db_path,
    )
    generation_root = index_dir / kernel_embeddings.GENERATION_ROOT_DIRNAME
    previous_generation_ids = {
        path.name for path in generation_root.iterdir() if path.is_dir()
    }

    real_atomic_copy_file = kernel_embeddings._atomic_copy_file

    def fail_legacy_index_copy(source: Path, target: Path) -> None:
        if target == legacy_index:
            raise OSError("synthetic compatibility index-copy failure")
        real_atomic_copy_file(source, target)

    monkeypatch.setattr(kernel_embeddings, "_atomic_copy_file", fail_legacy_index_copy)
    with pytest.raises(OSError, match="compatibility index-copy failure"):
        build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v2",
            embedding_device="cpu",
        )

    selected = kernel_embeddings.resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings,
        legacy_index_path=legacy_index,
    )
    assert selected is not None
    assert selected.selected is True
    assert selected.status == "complete"
    new_generation_dirs = [
        path
        for path in generation_root.iterdir()
        if path.is_dir() and path.name not in previous_generation_ids
    ]
    assert len(new_generation_dirs) == 1
    published_generation_dir = new_generation_dirs[0]
    published_inventory_bytes = (published_generation_dir / "inventory.json").read_bytes()
    published_inventory = json.loads(published_inventory_bytes)
    assert published_inventory["generation_id"] == published_generation_dir.name
    assert published_inventory["status"] == "complete"
    assert published_inventory["embedding_model"] == "fake-model@v2"
    assert published_inventory["embedding_device"] == "cpu"
    assert published_inventory["ids"] == ["ds-2"]
    assert published_inventory["basis"]["members"] == [
        {
            "identifier": "ds-2",
            "content_identity": "sha256:" + hashlib.sha256(b"New XYZ").hexdigest(),
        }
    ]
    with np.load(selected_previous.embeddings_path, allow_pickle=True) as old_payload:
        old_ids = old_payload["ids"].tolist()
        old_vectors = np.asarray(old_payload["vectors"], dtype=np.float32)
    published_embeddings_path = published_generation_dir / "embeddings.npz"
    with np.load(published_embeddings_path, allow_pickle=True) as payload:
        new_ids = payload["ids"].tolist()
        query_vector = np.asarray(payload["vectors"][0], dtype=np.float32)
    assert old_ids == ["ds-1"]
    assert new_ids == ["ds-2"]
    assert published_embeddings_path.read_bytes() != selected_previous.embeddings_path.read_bytes()
    assert not np.array_equal(old_vectors[0], query_vector)
    assert float(np.dot(old_vectors[0], query_vector)) < 0.99
    with np.load(legacy_embeddings, allow_pickle=True) as payload:
        assert payload["ids"].tolist() == ["ds-2"]
    assert legacy_index.read_bytes() == previous_index_bytes

    store = DatasetCatalogStore(db_path, index_dir)
    try:
        assert store.has_vector_index() is True
        results = store.search_by_vector(query_vector, top_k=1, min_similarity=0.99)
        assert [result.id for result in results] == ["ds-2"]
        assert results[0].similarity >= 0.99
    finally:
        store.close()

    assert selected.generation_id != selected_previous.generation_id
    assert selected.generation_id == published_generation_dir.name
    assert selected.ids == ("ds-2",)
    selector_payload = json.loads(
        (index_dir / kernel_embeddings.GENERATION_SELECTOR_FILENAME).read_bytes()
    )
    assert selector_payload["generation_id"] == selected.generation_id
    inventory_bytes = (index_dir / str(selector_payload["inventory"])).read_bytes()
    assert inventory_bytes == published_inventory_bytes
    assert hashlib.sha256(inventory_bytes).hexdigest() == selector_payload["inventory_sha256"]
    assert published_inventory == selected.inventory

    monkeypatch.setattr(kernel_embeddings, "_atomic_copy_file", real_atomic_copy_file)
    assert (
        build_catalog_hnsw_index(
            db_path=db_path,
            index_dir=index_dir,
            embedding_model="fake-model@v2",
            embedding_device="cpu",
        )
        == 1
    )
    recovered = kernel_embeddings.resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings,
        legacy_index_path=legacy_index,
    )
    assert recovered is not None
    assert recovered.selected is True
    assert legacy_embeddings.read_bytes() == recovered.embeddings_path.read_bytes()
    assert legacy_index.read_bytes() == recovered.index_path.read_bytes()
