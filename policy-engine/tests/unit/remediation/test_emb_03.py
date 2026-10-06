"""EMB-03 witnesses for content-bound legal embedding reuse.

These tests intentionally exercise the legal batch owner rather than inspecting
sidecar keys in isolation.  A legal embedding may be reused only when the
projected text, encoder profile, projection rule, and current membership are
all bound to the same generation.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.legal.batch import embedder as legal_embedder
from polisyos.data_forge.kernel.embeddings import (
    derive_encoder_identity,
    resolve_embedding_generation,
)
from polisyos.lex.knowledge.store import LegalKnowledgeStore

pytestmark = pytest.mark.unit


class _FakeSentenceTransformer:
    """Deterministic encoder whose model name controls revision and dimension."""

    instances: ClassVar[list[_FakeSentenceTransformer]] = []
    asset_revision: ClassVar[int] = 0
    tokenizer_revision: ClassVar[int] = 0

    def __init__(self, model_name: str, device: str | None = None, **_kwargs: object) -> None:
        self.model_name = model_name
        self.device = device
        self.dimension = 5 if model_name.endswith("-dim5") else 4
        self.config = {"model_name": model_name, "dimension": self.dimension}
        self.tokenizer = _FakeTokenizer(_FakeSentenceTransformer.tokenizer_revision)
        self.encoded_texts: list[str] = []
        type(self).instances.append(self)

    def state_dict(self) -> dict[str, np.ndarray]:
        return {
            "encoder.weight": np.asarray(
                [self.dimension, _FakeSentenceTransformer.asset_revision],
                dtype=np.float32,
            )
        }

    def modules(self) -> list[_FakeSentenceTransformer]:
        return [self]

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar
        self.encoded_texts.extend(texts)
        rows: list[np.ndarray] = []
        revision_offset = (
            11.0 if self.model_name.startswith("model-b") else 0.0
        ) + float(_FakeSentenceTransformer.asset_revision + self.tokenizer.revision)
        for text in texts:
            base = float((sum(map(ord, str(text))) % 17) + 1) + revision_offset
            vector = np.arange(base, base + self.dimension, dtype=np.float32)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


class _FakeTokenizer:
    def __init__(self, revision: int) -> None:
        self.revision = revision

    def get_vocab(self) -> dict[str, int]:
        return {"<unk>": 0, "legal": 1, f"revision-{self.revision}": 2}

    @property
    def special_tokens_map(self) -> dict[str, str]:
        return {"unk_token": "<unk>"}

    def get_added_vocab(self) -> dict[str, int]:
        return {}


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
    _FakeSentenceTransformer.asset_revision = 0
    _FakeSentenceTransformer.tokenizer_revision = 0
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer),
    )


def _prepare_lex_db(db_path: Path, *, entities: list[tuple[str, str]]) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE lex_entities ("
            "entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, "
            "entity_type VARCHAR, aliases_en VARCHAR, aliases_uk VARCHAR)"
        )
        for entity_id, name in entities:
            con.execute(
                "INSERT INTO lex_entities VALUES (?, ?, ?, ?, ?, ?)",
                [entity_id, name, name, "concept", "", ""],
            )
        con.execute(
            "CREATE TABLE lex_facts ("
            "fact_id VARCHAR, subject_en VARCHAR, subject_uk VARCHAR, predicate VARCHAR, "
            "object_en VARCHAR, object_uk VARCHAR, fact_text VARCHAR, norm_type VARCHAR, "
            "action_canon VARCHAR, norm_type_canon VARCHAR, condition_text_uk VARCHAR, "
            "exception_text_uk VARCHAR, procedure_text_uk VARCHAR, thresholds_json VARCHAR, "
            "source_quote_uk VARCHAR)"
        )
        con.execute("CREATE TABLE lex_provisions (provision_id VARCHAR, provision_text VARCHAR)")
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _replace_entity_name(db_path: Path, entity_id: str, name: str) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "UPDATE lex_entities SET name_en = ?, name_uk = ? WHERE entity_id = ?",
            [name, name, entity_id],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _add_entity(db_path: Path, entity_id: str, name: str) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO lex_entities VALUES (?, ?, ?, ?, ?, ?)",
            [entity_id, name, name, "concept", "", ""],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _remove_entity(db_path: Path, entity_id: str) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute("DELETE FROM lex_entities WHERE entity_id = ?", [entity_id])
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _replace_legal_records(
    db_path: Path,
    *,
    entity_id: str,
    entity_name: str,
    fact_id: str,
    fact_text: str,
    provision_id: str,
    provision_text: str,
) -> None:
    con = duckdb.connect(str(db_path))
    try:
        con.execute("DELETE FROM lex_entities")
        con.execute("DELETE FROM lex_facts")
        con.execute("DELETE FROM lex_provisions")
        con.execute(
            "INSERT INTO lex_entities VALUES (?, ?, ?, ?, ?, ?)",
            [entity_id, entity_name, entity_name, "concept", "", ""],
        )
        con.execute(
            "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                fact_id,
                "Subject",
                "Subiekt",
                "requires",
                "Benefit",
                "Пільга",
                fact_text,
                "obligation",
                "requires",
                "obligation",
                "",
                "",
                "",
                "[]",
                "source quote",
            ],
        )
        con.execute(
            "INSERT INTO lex_provisions VALUES (?, ?)",
            [provision_id, provision_text],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _entity_ids(output_dir: Path) -> list[str]:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return [str(value) for value in payload["ids"]]


def _entity_vectors(output_dir: Path) -> np.ndarray:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return np.asarray(payload["vectors"], dtype=np.float32).copy()


def _selected_legal_vectors(output_dir: Path, embedding_name: str) -> tuple[list[str], np.ndarray]:
    index_dir = output_dir / ".legal_embedding_generations" / embedding_name
    selector = json.loads((index_dir / "embedding_generation.json").read_text(encoding="utf-8"))
    generation_dir = index_dir / "embedding_generations" / str(selector["generation_id"])
    with np.load(generation_dir / "embeddings.npz", allow_pickle=True) as payload:
        ids = [str(value) for value in payload["ids"].tolist()]
        vectors = np.asarray(payload["vectors"], dtype=np.float32).copy()
    return ids, vectors


def _generation_selectors(output_dir: Path) -> list[Path]:
    return sorted(output_dir.rglob("embedding_generation.json"))


def test_unchanged_append_reuses_only_unchanged_current_member(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget")])

    first = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    _add_entity(db_path, "e2", "Tax")
    second = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert first.entities_embedded == 1
    assert second.entities_embedded == 1
    assert second.entities_skipped == 1
    assert _entity_ids(tmp_path) == ["e1", "e2"]
    assert len(_generation_selectors(tmp_path)) == 3


def test_changed_projected_text_same_id_is_reembedded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget")])

    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    before = _entity_vectors(tmp_path)
    _replace_entity_name(db_path, "e1", "Changed budget")
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 1
    assert stats.entities_skipped == 0
    assert not np.array_equal(before, _entity_vectors(tmp_path))


def test_withdrawal_removes_id_from_current_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget"), ("e2", "Tax")])

    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    _remove_entity(db_path, "e2")
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 0
    assert stats.entities_skipped == 1
    assert _entity_ids(tmp_path) == ["e1"]


def test_encoder_revision_and_dimension_change_never_reuses_old_vectors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget"), ("e2", "Tax")])

    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-b-dim5",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 2
    assert stats.entities_skipped == 0
    assert _entity_vectors(tmp_path).shape == (2, 5)


def test_same_model_label_and_dimension_with_changed_loaded_weights_invalidates_reuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget"), ("e2", "Tax")])
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    before = _entity_vectors(tmp_path)

    _FakeSentenceTransformer.asset_revision = 7
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 2
    assert stats.entities_skipped == 0
    assert not np.array_equal(before, _entity_vectors(tmp_path))


def test_same_model_label_and_dimension_with_changed_tokenizer_invalidates_reuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget"), ("e2", "Tax")])
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    before = _entity_vectors(tmp_path)

    _FakeSentenceTransformer.tokenizer_revision = 1
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 2
    assert stats.entities_skipped == 0
    assert not np.array_equal(before, _entity_vectors(tmp_path))


def test_legal_entity_fact_and_provision_readers_follow_selected_membership(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[])
    _replace_legal_records(
        db_path,
        entity_id="e-old",
        entity_name="Old entity",
        fact_id="f-old",
        fact_text="Old fact text",
        provision_id="p-old",
        provision_text="Old provision text",
    )
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    old_embeddings = {
        name: _selected_legal_vectors(tmp_path, name)[1][0].copy()
        for name in (
            "lex_entity_embeddings",
            "lex_fact_embeddings",
            "lex_provision_embeddings",
        )
    }

    _replace_legal_records(
        db_path,
        entity_id="e-old",
        entity_name="Changed entity text",
        fact_id="f-old",
        fact_text="Changed fact text",
        provision_id="p-old",
        provision_text="Changed provision text",
    )
    stale_reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        assert stale_reader.search_entities_by_vector(
            old_embeddings["lex_entity_embeddings"], min_similarity=0.0
        ) == []
        assert stale_reader.search_facts_by_vector(
            old_embeddings["lex_fact_embeddings"], min_similarity=0.0, include_candidates=True
        ) == []
        assert stale_reader.search_provisions_by_vector(
            old_embeddings["lex_provision_embeddings"], min_similarity=0.0
        ) == []
    finally:
        stale_reader.close()

    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )
    assert (stats.entities_embedded, stats.facts_embedded, stats.provisions_embedded) == (1, 1, 1)
    assert (stats.entities_skipped, stats.facts_skipped, stats.provisions_skipped) == (0, 0, 0)

    selected: dict[str, np.ndarray] = {}
    for name, expected_id in (
        ("lex_entity_embeddings", "e-old"),
        ("lex_fact_embeddings", "f-old"),
        ("lex_provision_embeddings", "p-old"),
    ):
        ids, vectors = _selected_legal_vectors(tmp_path, name)
        assert ids == [expected_id]
        selected[name] = vectors[0]
    reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        assert [
            result.entity_id
            for result in reader.search_entities_by_vector(
                selected["lex_entity_embeddings"], min_similarity=0.0
            )
        ] == ["e-old"]
        assert [
            result.fact_id
            for result in reader.search_facts_by_vector(
                selected["lex_fact_embeddings"], min_similarity=0.0, include_candidates=True
            )
        ] == ["f-old"]
        assert [
            result.provision_id
            for result in reader.search_provisions_by_vector(
                selected["lex_provision_embeddings"], min_similarity=0.0
            )
        ] == ["p-old"]
    finally:
        reader.close()

    con = duckdb.connect(str(db_path))
    try:
        con.execute("DELETE FROM lex_entities")
        con.execute("DELETE FROM lex_facts")
        con.execute("DELETE FROM lex_provisions")
        con.execute("CHECKPOINT")
    finally:
        con.close()

    withdrawn_reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        assert withdrawn_reader.search_entities_by_vector(
            selected["lex_entity_embeddings"], min_similarity=0.0
        ) == []
        assert withdrawn_reader.search_facts_by_vector(
            selected["lex_fact_embeddings"], min_similarity=0.0, include_candidates=True
        ) == []
        assert withdrawn_reader.search_provisions_by_vector(
            selected["lex_provision_embeddings"], min_similarity=0.0
        ) == []
    finally:
        withdrawn_reader.close()

    empty_stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )
    assert (
        empty_stats.entities_embedded,
        empty_stats.facts_embedded,
        empty_stats.provisions_embedded,
    ) == (0, 0, 0)
    assert (
        empty_stats.entities_skipped,
        empty_stats.facts_skipped,
        empty_stats.provisions_skipped,
    ) == (0, 0, 0)


def test_projection_rule_change_invalidates_reuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget")])

    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    legal_embedder.LEGAL_EMBEDDING_PROJECTION_RULE_VERSION = "policyos.legal.embedding.v2"
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 1
    assert stats.entities_skipped == 0


def test_missing_or_corrupt_generation_selector_fails_closed_to_rebuild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("e1", "Budget")])

    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
    )
    selectors = _generation_selectors(tmp_path)
    assert selectors
    selectors[0].write_text("{not-json", encoding="utf-8")
    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="model-a",
        embedding_device="cpu",
        incremental=True,
    )

    assert stats.entities_embedded == 1
    assert stats.entities_skipped == 0


def test_legacy_backend_argument_is_rejected_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def _unexpected(**_kwargs: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(legal_embedder, "build_local_embeddings_and_indexes", _unexpected)
    with pytest.raises(ValueError, match="unsupported backend"):
        legal_embedder.build_embeddings_and_index(Path("db"), Path("out"), backend=object())
    assert called is False


def test_legacy_wrapper_preserves_canonical_result_and_forwards_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    captured: dict[str, object] = {}

    def _canonical(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(legal_embedder, "build_local_embeddings_and_indexes", _canonical)
    result = legal_embedder.build_embeddings_and_index(
        Path("db"),
        Path("out"),
        chunk_size=17,
    )

    assert result is sentinel
    assert captured["db_path"] == Path("db")
    assert captured["output_dir"] == Path("out")
    assert captured["embedding_model"] == "intfloat/multilingual-e5-large"
    assert captured["embedding_device"] == "mps"
    assert captured["embedding_chunk_size"] == 17


def test_legacy_entrypoint_uses_supported_encoder_and_legal_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_sentence_transformer(monkeypatch)
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-1", "recorded encoder target")])
    encoder = _FakeSentenceTransformer("legacy-recording-model", device="cpu")

    stats = legal_embedder.build_embeddings_and_index(
        db_path,
        tmp_path,
        backend=encoder,
        chunk_size=1,
    )

    assert stats.entities_embedded == 1
    assert encoder.encoded_texts
    assert _FakeSentenceTransformer.instances == [encoder]
    generation_dir = tmp_path / ".legal_embedding_generations" / "lex_entity_embeddings"
    reference = resolve_embedding_generation(
        generation_dir,
        legacy_embeddings_path=tmp_path / "lex_entity_embeddings.npz",
        legacy_index_path=tmp_path / "lex_entity_index.hnsw",
    )
    assert reference is not None
    assert reference.status == "complete"
    rule_version = reference.inventory["basis"]["generator_rule_version"]
    assert derive_encoder_identity(encoder).content_identity in rule_version
    with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
        query = np.asarray(payload["vectors"][0], dtype=np.float32)

    reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        results = reader.search_entities_by_vector(query, top_k=1, min_similarity=0.0)
    finally:
        reader.close()
    assert [result.entity_id for result in results] == ["entity-1"]
