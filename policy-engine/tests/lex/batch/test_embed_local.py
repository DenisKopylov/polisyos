from __future__ import annotations

import types

import duckdb
import numpy as np

from polisyos.lex.batch.embedder import build_local_embeddings_and_indexes


class _FakeSentenceTransformer:
    def __init__(self, model_name: str, device: str | None = None) -> None:
        self._dim = 4

    def get_sentence_embedding_dimension(self) -> int:
        return self._dim

    def encode(self, texts, batch_size: int = 32, show_progress_bar: bool = False, normalize_embeddings: bool = True):
        rows = []
        for idx, text in enumerate(texts):
            base = float((len(str(text)) % 7) + 1)
            vec = np.array([base, base + 1, base + 2, base + 3], dtype=np.float32)
            if normalize_embeddings:
                vec = vec / np.linalg.norm(vec)
            rows.append(vec)
        return np.vstack(rows)


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
