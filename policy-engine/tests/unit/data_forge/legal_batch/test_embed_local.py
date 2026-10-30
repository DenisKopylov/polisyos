from __future__ import annotations

import types

import duckdb
import numpy as np

from polisyos.data_forge.domains.legal.batch.embedder import build_local_embeddings_and_indexes
from polisyos.data_forge.domains.legal.embedding_projection import (
    LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
    entity_embedding_text,
    fact_embedding_text,
    provision_embedding_text,
)
from polisyos.data_forge.kernel.embeddings import (
    build_embedding_index,
    embedding_generation_matches_encoder,
    resolve_embedding_generation,
)
from polisyos.data_forge.kernel.io.generation_basis import (
    generation_basis_matches_members,
)


class _FakeSentenceTransformer:
    def __init__(self, model_name: str, device: str | None = None) -> None:
        self._dim = 4
        self.device = device or "cpu"
        self.config = {"model_name": model_name, "dimension": self._dim}
        self.tokenizer = _FakeTokenizer()

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": np.asarray([self._dim], dtype=np.float32)}

    def modules(self) -> list[_FakeSentenceTransformer]:
        return [self]

    def get_sentence_embedding_dimension(self) -> int:
        return self._dim

    def encode(
        self,
        texts,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ):
        rows = []
        for _idx, text in enumerate(texts):
            base = float((len(str(text)) % 7) + 1)
            vec = np.array([base, base + 1, base + 2, base + 3], dtype=np.float32)
            if normalize_embeddings:
                vec = vec / np.linalg.norm(vec)
            rows.append(vec)
        return np.vstack(rows)


class _FakeTokenizer:
    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, "legal": 1}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


def _prepare_lex_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE lex_entities (entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, entity_type VARCHAR, aliases_en VARCHAR, aliases_uk VARCHAR)"
        )
        con.execute(
            "INSERT INTO lex_entities VALUES ('e1','Budget','Бюджет','concept','Budget plan','План бюджету')"
        )

        con.execute(
            "CREATE TABLE lex_facts ("
            "fact_id VARCHAR, subject_en VARCHAR, subject_uk VARCHAR, predicate VARCHAR, "
            "object_en VARCHAR, object_uk VARCHAR, fact_text VARCHAR, norm_type VARCHAR, "
            "action_canon VARCHAR, norm_type_canon VARCHAR, condition_text_uk VARCHAR, "
            "exception_text_uk VARCHAR, procedure_text_uk VARCHAR, thresholds_json VARCHAR, source_quote_uk VARCHAR)"
        )
        con.execute(
            "INSERT INTO lex_facts VALUES ('f1','State','Держава','sets','Tax','Податок','State sets tax','obligation','sets','obligation','','','','{}','quote')"
        )

        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR, provision_text VARCHAR)")
        con.execute("INSERT INTO lex_provisions VALUES ('p1','Стаття 1. Тестова норма')")
        con.execute("CHECKPOINT")
    finally:
        con.close()


def test_build_local_embeddings_and_indexes(monkeypatch, tmp_path) -> None:
    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_lex_db(db_path)

    stats = build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="fake-model",
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=10,
    )

    assert stats.entities_embedded == 1
    assert stats.facts_embedded == 1
    assert stats.provisions_embedded == 1

    assert (tmp_path / "lex_entity_embeddings.npz").exists()
    assert (tmp_path / "lex_entity_index.hnsw").exists()
    assert (tmp_path / "lex_fact_embeddings.npz").exists()
    assert (tmp_path / "lex_fact_index.hnsw").exists()
    assert (tmp_path / "lex_provision_embeddings.npz").exists()
    assert (tmp_path / "lex_provision_index.hnsw").exists()


def test_legacy_flat_pair_rebuilds_changed_text_then_reuses_current_membership(
    monkeypatch, tmp_path
) -> None:
    import hnswlib

    fake_module = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", fake_module)

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_lex_db(db_path)

    def _write_provisions(rows) -> None:
        con = duckdb.connect(str(db_path))
        try:
            con.execute("DELETE FROM lex_entities")
            con.execute("DELETE FROM lex_facts")
            con.execute("DELETE FROM lex_provisions")
            for identifier, text in rows:
                con.execute("INSERT INTO lex_provisions VALUES (?, ?)", [identifier, text])
            con.execute("CHECKPOINT")
        finally:
            con.close()

    def _resolve_provisions():
        reference = resolve_embedding_generation(
            tmp_path / ".legal_embedding_generations" / "lex_provision_embeddings",
            legacy_embeddings_path=tmp_path / "lex_provision_embeddings.npz",
            legacy_index_path=tmp_path / "lex_provision_index.hnsw",
        )
        assert reference is not None
        return reference

    def _assert_rows_and_hnsw(reference, expected_vectors):
        with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
            ids = tuple(str(value) for value in payload["ids"].tolist())
            matrix = np.asarray(payload["vectors"], dtype=np.float32)
        assert ids == reference.ids == tuple(expected_vectors)
        assert matrix.shape == (len(ids), reference.dimension)
        for row_number, identifier in enumerate(ids):
            assert np.array_equal(matrix[row_number], expected_vectors[identifier])

        assert reference.index_path is not None
        index = hnswlib.Index(space="cosine", dim=reference.dimension)
        index.load_index(str(reference.index_path))
        labels, distances = index.knn_query(matrix, k=1)
        assert labels[:, 0].tolist() == list(range(len(ids)))
        assert np.allclose(distances[:, 0], 0.0, atol=1e-6)
        return {identifier: matrix[row_number] for row_number, identifier in enumerate(ids)}

    def _assert_selected_generation(reference, rows, encoder):
        assert reference.selected is True
        assert reference.status == "complete"
        assert reference.ids == tuple(identifier for identifier, _text in rows)
        assert generation_basis_matches_members(
            reference,
            basis_kind="legal_lex_provisions_embedding",
            members=[
                (identifier, provision_embedding_text((text,)).encode("utf-8"))
                for identifier, text in rows
            ],
        )
        assert embedding_generation_matches_encoder(
            reference,
            encoder=encoder,
            basis_kind="legal_lex_provisions_embedding",
            projection_rule_version=LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
            embedding_model="fake-model",
            embedding_device="cpu",
            embedding_dimension=4,
        )
        expected = {identifier: encoder.vectors_by_text[text] for identifier, text in rows}
        return _assert_rows_and_hnsw(reference, expected)

    def _generation_snapshot(reference):
        assert reference.selected is True
        assert reference.status == "complete"
        assert reference.inventory_path is not None
        generation_dir = reference.inventory_path.parent
        assert generation_dir == reference.root_dir
        assert generation_dir.name == reference.generation_id
        return {
            path.name: path.read_bytes()
            for path in sorted(generation_dir.iterdir())
            if path.is_file()
        }

    legacy_rows = [("p1", "old id one"), ("p2", "stable id two")]
    _write_provisions(legacy_rows)
    legacy_npz = tmp_path / "lex_provision_embeddings.npz"
    legacy_hnsw = tmp_path / "lex_provision_index.hnsw"
    assert build_embedding_index(
        rows=legacy_rows,
        embeddings_path=legacy_npz,
        index_path=legacy_hnsw,
        embedding_model="fake-model",
        embedding_device="cpu",
        embedding_dimension=4,
        embedding_batch_size=2,
    ) == (2, 4)

    selector = (
        tmp_path
        / ".legal_embedding_generations"
        / "lex_provision_embeddings"
        / "embedding_generation.json"
    )
    assert not selector.exists()
    legacy = _resolve_provisions()
    assert legacy.generation_id == "legacy-flat"
    assert legacy.status == "legacy"
    assert legacy.selected is False
    legacy_matrix = _FakeSentenceTransformer("fake-model", device="cpu").encode(
        [text for _identifier, text in legacy_rows],
        batch_size=2,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    legacy_vectors = {
        identifier: legacy_matrix[row_number]
        for row_number, (identifier, _text) in enumerate(legacy_rows)
    }
    _assert_rows_and_hnsw(legacy, legacy_vectors)

    class _RecordingEncoder(_FakeSentenceTransformer):
        def __init__(self, model_name: str, device: str | None = None) -> None:
            super().__init__(model_name, device=device)
            self.encoded_batches: list[tuple[str, ...]] = []
            self.vectors_by_text: dict[str, np.ndarray] = {}

        def encode(
            self,
            texts,
            batch_size: int = 32,
            show_progress_bar: bool = False,
            normalize_embeddings: bool = True,
        ):
            text_values = tuple(str(text) for text in texts)
            vectors = super().encode(
                text_values,
                batch_size=batch_size,
                show_progress_bar=show_progress_bar,
                normalize_embeddings=normalize_embeddings,
            )
            self.encoded_batches.append(text_values)
            self.vectors_by_text.update(
                (text, vectors[row_number].copy()) for row_number, text in enumerate(text_values)
            )
            return vectors

    encoder = _RecordingEncoder("fake-model", device="cpu")
    initial_rows = [
        ("p1", "new id one text"),
        ("p2", "stable id two"),
        ("p3", "fresh id three"),
    ]
    _write_provisions(initial_rows)
    first_stats = build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="fake-model",
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=10,
        incremental=True,
        encoder=encoder,
    )
    assert first_stats.provisions_embedded == 3
    assert first_stats.provisions_skipped == 0
    # Pin the provisions batch explicitly; this fixture leaves entity and fact
    # projections empty and makes no mixed-projection call-count claim.
    assert encoder.encoded_batches[-1] == tuple(text for _identifier, text in initial_rows)

    first = _resolve_provisions()
    assert first.generation_id != legacy.generation_id
    first_vectors = _assert_selected_generation(first, initial_rows, encoder)
    assert not np.array_equal(legacy_vectors["p1"], first_vectors["p1"])
    first_history = _generation_snapshot(first)

    appended_rows = [*initial_rows, ("p4", "fresh id four!!!")]
    _write_provisions(appended_rows)
    second_stats = build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="fake-model",
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=10,
        incremental=True,
        encoder=encoder,
    )
    assert second_stats.provisions_embedded == 1
    assert second_stats.provisions_skipped == 3
    assert encoder.encoded_batches[-1] == ("fresh id four!!!",)

    second = _resolve_provisions()
    assert second.generation_id != first.generation_id
    second_vectors = _assert_selected_generation(second, appended_rows, encoder)
    for identifier in ("p1", "p2", "p3"):
        assert np.array_equal(first_vectors[identifier], second_vectors[identifier])
    second_history = _generation_snapshot(second)
    assert _generation_snapshot(first) == first_history

    withdrawn_rows = [
        ("p1", "new id one text"),
        ("p3", "fresh id three"),
        ("p4", "fresh id four!!!"),
    ]
    _write_provisions(withdrawn_rows)
    prior_batch_count = len(encoder.encoded_batches)
    third_stats = build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="fake-model",
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=10,
        incremental=True,
        encoder=encoder,
    )
    assert third_stats.provisions_embedded == 0
    assert third_stats.provisions_skipped == 3
    assert len(encoder.encoded_batches) == prior_batch_count

    third = _resolve_provisions()
    assert third.generation_id != second.generation_id
    assert third.ids == ("p1", "p3", "p4")
    assert "p2" in second.ids
    assert "p2" not in third.ids
    third_vectors = _assert_selected_generation(third, withdrawn_rows, encoder)
    for identifier in ("p1", "p3", "p4"):
        assert np.array_equal(second_vectors[identifier], third_vectors[identifier])
    assert _generation_snapshot(first) == first_history
    assert _generation_snapshot(second) == second_history


def test_all_selected_legal_projections_reuse_changed_and_withdrawn_members(tmp_path) -> None:
    """Each projection must recompute edited rows and exclude withdrawn IDs."""
    import hnswlib

    class RecordingEncoder(_FakeSentenceTransformer):
        def __init__(self) -> None:
            super().__init__("fixture-model", device="cpu")
            self.batches: list[tuple[str, ...]] = []

        def encode(
            self,
            texts,
            batch_size: int = 32,
            show_progress_bar: bool = False,
            normalize_embeddings: bool = True,
        ):
            self.batches.append(tuple(texts))
            return super().encode(texts, batch_size, show_progress_bar, normalize_embeddings)

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_lex_db(db_path)
    with duckdb.connect(str(db_path)) as con:
        for query, prefix in (
            (
                "INSERT INTO lex_entities SELECT ?, * EXCLUDE (entity_id) "
                "FROM lex_entities WHERE entity_id = ?",
                "e",
            ),
            (
                "INSERT INTO lex_facts SELECT ?, * EXCLUDE (fact_id) "
                "FROM lex_facts WHERE fact_id = ?",
                "f",
            ),
            (
                "INSERT INTO lex_provisions SELECT ?, * EXCLUDE (provision_id) "
                "FROM lex_provisions WHERE provision_id = ?",
                "p",
            ),
        ):
            for suffix in ("2", "3"):
                con.execute(query, [prefix + suffix, prefix + "1"])

    encoder = RecordingEncoder()

    def build():
        return build_local_embeddings_and_indexes(
            db_path=db_path,
            output_dir=tmp_path,
            embedding_model="fixture-model",
            embedding_device="cpu",
            embedding_batch_size=2,
            embedding_chunk_size=10,
            incremental=True,
            encoder=encoder,
        )

    projections = (
        (
            "lex_entity_embeddings",
            "lex_entity_index",
            "SELECT entity_id, name_en, name_uk, entity_type, aliases_en, aliases_uk "
            "FROM lex_entities ORDER BY entity_id",
            entity_embedding_text,
            "e",
        ),
        (
            "lex_fact_embeddings",
            "lex_fact_index",
            "SELECT fact_id, subject_en, subject_uk, predicate, object_en, object_uk, "
            "fact_text, norm_type, action_canon, norm_type_canon, condition_text_uk, "
            "exception_text_uk, procedure_text_uk, thresholds_json, source_quote_uk "
            "FROM lex_facts ORDER BY fact_id",
            fact_embedding_text,
            "f",
        ),
        (
            "lex_provision_embeddings",
            "lex_provision_index",
            "SELECT provision_id, provision_text FROM lex_provisions ORDER BY provision_id",
            provision_embedding_text,
            "p",
        ),
    )

    def selected(name, index_name):
        reference = resolve_embedding_generation(
            tmp_path / ".legal_embedding_generations" / name,
            legacy_embeddings_path=tmp_path / f"{name}.npz",
            legacy_index_path=tmp_path / f"{index_name}.hnsw",
        )
        assert reference is not None and reference.selected and reference.status == "complete"
        with np.load(reference.embeddings_path, allow_pickle=True) as payload:
            ids = tuple(str(value) for value in payload["ids"].tolist())
            matrix = np.asarray(payload["vectors"], dtype=np.float32).copy()
        assert ids == reference.ids
        assert reference.index_path is not None
        index = hnswlib.Index(space="cosine", dim=reference.dimension)
        index.load_index(str(reference.index_path))
        assert set(index.get_ids_list()) == set(range(len(ids)))
        assert np.allclose(index.get_items(list(range(len(ids)))), matrix, atol=1e-6)
        return ids, matrix

    initial = build()
    assert (initial.entities_embedded, initial.facts_embedded, initial.provisions_embedded) == (
        3,
        3,
        3,
    )
    before = {name: selected(name, index_name) for name, index_name, *_rest in projections}
    encoder.batches.clear()
    unchanged = build()
    assert (unchanged.entities_skipped, unchanged.facts_skipped, unchanged.provisions_skipped) == (
        3,
        3,
        3,
    )
    assert not encoder.batches

    with duckdb.connect(str(db_path)) as con:
        con.execute("UPDATE lex_entities SET name_en = name_en || 'xx' WHERE entity_id = 'e1'")
        con.execute("UPDATE lex_facts SET fact_text = fact_text || 'xx' WHERE fact_id = 'f1'")
        con.execute(
            "UPDATE lex_provisions SET provision_text = provision_text || 'xx' "
            "WHERE provision_id = 'p1'"
        )
        con.execute("DELETE FROM lex_entities WHERE entity_id = 'e3'")
        con.execute("DELETE FROM lex_facts WHERE fact_id = 'f3'")
        con.execute("DELETE FROM lex_provisions WHERE provision_id = 'p3'")

    rebuilt = build()
    assert (rebuilt.entities_embedded, rebuilt.facts_embedded, rebuilt.provisions_embedded) == (
        1,
        1,
        1,
    )
    assert (rebuilt.entities_skipped, rebuilt.facts_skipped, rebuilt.provisions_skipped) == (
        1,
        1,
        1,
    )
    expected_batches = []
    for name, index_name, query, project, prefix in projections:
        ids, matrix = selected(name, index_name)
        assert ids == (prefix + "1", prefix + "2")
        old_ids, old_matrix = before[name]
        assert old_ids == (prefix + "1", prefix + "2", prefix + "3")
        assert np.array_equal(matrix[1], old_matrix[1])
        assert not np.array_equal(matrix[0], old_matrix[0])
        with duckdb.connect(str(db_path), read_only=True) as con:
            rows = con.execute(query).fetchall()
        edited_text = project(rows[0][1:])
        expected_batches.append((edited_text,))
        base = float((len(edited_text) % 7) + 1)
        expected = np.asarray([base, base + 1, base + 2, base + 3], dtype=np.float32)
        expected /= np.linalg.norm(expected)
        assert np.allclose(matrix[0], expected)
    assert encoder.batches == expected_batches
