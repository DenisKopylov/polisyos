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
from typing import ClassVar, cast

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.legal.batch import embedder as legal_embedder
from polisyos.data_forge.kernel.embeddings import (
    derive_encoder_identity,
    resolve_embedding_generation,
)
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.knowledge.store import (
    LegalKnowledgeStore,
    LegalQueryInput,
    LegalQueryProfile,
    LegalQueryProfileError,
)

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
        revision_offset = (11.0 if self.model_name.startswith("model-b") else 0.0) + float(
            _FakeSentenceTransformer.asset_revision + self.tokenizer.revision
        )
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


class _DirectionalLegalEncoder:
    """Small same-dimension encoder whose revision changes target direction."""

    def __init__(self, *, revision: int, device: str = "cpu") -> None:
        self.revision = revision
        self.device = device
        self.model_name = "legal-fixture-model"
        self.dimension = 4
        self.config = {"model_name": self.model_name, "dimension": self.dimension}
        self.tokenizer = _FakeTokenizer(0)
        self.encoded_texts: list[str] = []

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": np.asarray([self.revision], dtype=np.float32)}

    def modules(self) -> list[_DirectionalLegalEncoder]:
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
        target_axis = 0 if self.revision == 0 else 1
        decoy_axis = 1 - target_axis
        rows = []
        for text in texts:
            is_target = "target" in str(text).lower()
            vector = np.zeros(self.dimension, dtype=np.float32)
            vector[target_axis if is_target else decoy_axis] = 1.0
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


class _MutatingLegalEncoder(_DirectionalLegalEncoder):
    """Change live weights during query encoding to exercise request binding."""

    def __init__(
        self,
        *,
        revision: int,
        device: str = "cpu",
        mutate_during_encode: bool = False,
    ) -> None:
        super().__init__(revision=revision, device=device)
        self.mutate_during_encode = mutate_during_encode

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        vectors = super().encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=normalize_embeddings,
        )
        if self.mutate_during_encode:
            self.revision = 1
        return vectors


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


def _prepare_legal_search_rows(db_path: Path) -> None:
    """Add target and decoy facts/provisions to the minimal legal fixture."""
    con = duckdb.connect(str(db_path))
    try:
        for fact_id, label in (("fact-target", "target"), ("fact-decoy", "decoy")):
            con.execute(
                "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    fact_id,
                    label.title(),
                    label.title(),
                    "describes",
                    "record",
                    "запис",
                    f"{label} fact text",
                    "obligation",
                    "describes",
                    "obligation",
                    "",
                    "",
                    "",
                    "[]",
                    f"{label} quote",
                ],
            )
        for provision_id, label in (("provision-target", "target"), ("provision-decoy", "decoy")):
            con.execute(
                "INSERT INTO lex_provisions VALUES (?, ?)",
                [provision_id, f"{label} provision text"],
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


def _legal_query_profile(output_dir: Path) -> tuple[LegalQueryProfile, ...]:
    """Freeze fixture request intent from existing selected generation refs."""
    profiles: list[LegalQueryProfile] = []
    for embedding_name, index_name in (
        ("lex_entity_embeddings", "lex_entity_index"),
        ("lex_fact_embeddings", "lex_fact_index"),
        ("lex_provision_embeddings", "lex_provision_index"),
    ):
        generation = resolve_embedding_generation(
            output_dir / ".legal_embedding_generations" / embedding_name,
            legacy_embeddings_path=output_dir / f"{embedding_name}.npz",
            legacy_index_path=output_dir / f"{index_name}.hnsw",
        )
        if generation is not None and generation.status == "complete":
            profiles.append(LegalQueryProfile.from_generation(generation))
    return tuple(profiles)


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
    query_encoder = _FakeSentenceTransformer.instances[-1]

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
        assert (
            stale_reader.search_entities_by_vector(
                LegalQueryInput(
                    "Old entity", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
            )
            == []
        )
        assert (
            stale_reader.search_facts_by_vector(
                LegalQueryInput(
                    "Old fact text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0,
                include_candidates=True,
            )
            == []
        )
        assert (
            stale_reader.search_provisions_by_vector(
                LegalQueryInput(
                    "Old provision text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
            )
            == []
        )
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

    reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        assert [
            result.entity_id
            for result in reader.search_entities_by_vector(
                LegalQueryInput(
                    "Changed entity text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
            )
        ] == ["e-old"]
        assert [
            result.fact_id
            for result in reader.search_facts_by_vector(
                LegalQueryInput(
                    "Changed fact text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0,
                include_candidates=True,
            )
        ] == ["f-old"]
        assert [
            result.provision_id
            for result in reader.search_provisions_by_vector(
                LegalQueryInput(
                    "Changed provision text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
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
        assert (
            withdrawn_reader.search_entities_by_vector(
                LegalQueryInput(
                    "Changed entity text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
            )
            == []
        )
        assert (
            withdrawn_reader.search_facts_by_vector(
                LegalQueryInput(
                    "Changed fact text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0,
                include_candidates=True,
            )
            == []
        )
        assert (
            withdrawn_reader.search_provisions_by_vector(
                LegalQueryInput(
                    "Changed provision text", query_encoder, _legal_query_profile(tmp_path)
                ),
                min_similarity=0.0
            )
            == []
        )
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
    monkeypatch.setattr(
        legal_embedder, "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION", "policyos.legal.embedding.v3"
    )
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

    reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        results = reader.search_entities_by_vector(
            LegalQueryInput("recorded encoder target", encoder, _legal_query_profile(tmp_path)),
            top_k=1,
            min_similarity=0.0
        )
    finally:
        reader.close()
    assert [result.entity_id for result in results] == ["entity-1"]


def test_graph_query_encoder_reads_all_three_selected_legal_generations(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(
        db_path,
        entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
    )
    _prepare_legal_search_rows(db_path)
    producer = _DirectionalLegalEncoder(revision=0)
    query_encoder = _DirectionalLegalEncoder(revision=0)

    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=producer,
    )

    assert (
        stats.entities_embedded,
        stats.facts_embedded,
        stats.provisions_embedded,
    ) == (2, 2, 2)
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        embedding_model="deprecated-label-is-not-request-intent",
        query_encoder=query_encoder,
        query_profile=_legal_query_profile(tmp_path),
    )
    try:
        assert [
            result.entity_id
            for result in graph.search_entities("target", top_k=1, min_similarity=0.0)
        ] == ["entity-target"]
        assert [
            result.fact_id
            for result in graph.search_facts(
                "target",
                top_k=1,
                min_similarity=0.0,
                trust_tier=None,
                include_candidates=True,
            )
        ] == ["fact-target"]
        assert [
            result.provision_id
            for result in graph.search_provisions("target", top_k=1, min_similarity=0.0)
        ] == ["provision-target"]
    finally:
        graph.close()


def test_live_query_encoder_must_match_selected_generation_before_knn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import hnswlib

    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(
        db_path,
        entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
    )
    _prepare_legal_search_rows(db_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )

    calls = 0
    original_knn_query = hnswlib.Index.knn_query

    def record_knn_query(index: object, *args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_knn_query(index, *args, **kwargs)

    monkeypatch.setattr(hnswlib.Index, "knn_query", record_knn_query)
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=_DirectionalLegalEncoder(revision=1),
        query_profile=_legal_query_profile(tmp_path),
    )
    try:
        with pytest.raises(LegalQueryProfileError, match="encoder_identity_mismatch"):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
    finally:
        graph.close()
    assert calls == 0
    assert graph.query_profile_error is not None
    assert graph.query_profile_error.code == "encoder_identity_mismatch"


def test_encoder_asset_change_during_query_encode_is_rejected_before_knn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import hnswlib

    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-target", "target entity")])
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_MutatingLegalEncoder(revision=0),
    )

    calls = 0
    original_knn_query = hnswlib.Index.knn_query

    def record_knn_query(index: object, *args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original_knn_query(index, *args, **kwargs)

    monkeypatch.setattr(hnswlib.Index, "knn_query", record_knn_query)
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=_MutatingLegalEncoder(revision=0, mutate_during_encode=True),
        query_profile=_legal_query_profile(tmp_path),
    )
    try:
        with pytest.raises(LegalQueryProfileError, match="query_encoder_changed_during_encode"):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
    finally:
        graph.close()
    assert calls == 0


def test_raw_vector_cannot_bypass_query_profile_gate_and_control_is_discriminating(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(
        db_path,
        entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
    )
    _prepare_legal_search_rows(db_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )
    reader = LegalKnowledgeStore(db_path, tmp_path)
    try:
        forged_vector = _DirectionalLegalEncoder(revision=1).encode(["target"])[0]
        with pytest.raises(LegalQueryProfileError, match="unbound_query_vector"):
            reader.search_entities_by_vector(
                cast("LegalQueryInput", forged_vector), top_k=1, min_similarity=0.0
            )

        # Remove only the intake gate while preserving the selected generation and
        # actual HNSW consumer. The same-dimensional wrong vector selects the decoy.
        reader._load_entity_index()
        assert reader._entity_index is not None
        assert reader._entity_ids is not None
        valid_query = LegalQueryInput(
            "target", _DirectionalLegalEncoder(revision=0), _legal_query_profile(tmp_path)
        )
        original_validator = reader._query_vector_for_generation
        monkeypatch.setattr(
            reader,
            "_query_vector_for_generation",
            lambda *_args, **_kwargs: forged_vector,
        )
        bypassed = reader.search_entities_by_vector(valid_query, top_k=1, min_similarity=0.0)
        assert [result.entity_id for result in bypassed] == ["entity-decoy"]
        monkeypatch.setattr(reader, "_query_vector_for_generation", original_validator)
        admitted = reader.search_entities_by_vector(valid_query, top_k=1, min_similarity=0.0)
        assert [result.entity_id for result in admitted] == ["entity-target"]
    finally:
        reader.close()


def test_wrong_selected_generation_rejects_previous_query_encoder(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-target", "target entity")])
    _prepare_legal_search_rows(db_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=_DirectionalLegalEncoder(revision=0),
        query_profile=_legal_query_profile(tmp_path),
    )
    try:
        assert graph.search_entities("target", top_k=1, min_similarity=0.0)

        legal_embedder.build_local_embeddings_and_indexes(
            db_path=db_path,
            output_dir=tmp_path,
            embedding_model="legal-fixture-model",
            embedding_device="cpu",
            encoder=_DirectionalLegalEncoder(revision=1),
            incremental=False,
        )
        with pytest.raises(LegalQueryProfileError, match="query_profile_stale_or_mismatched"):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
    finally:
        graph.close()


def test_concurrent_selector_replacement_keeps_query_on_one_generation(
    tmp_path: Path,
) -> None:
    from threading import Event, Thread

    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(
        db_path,
        entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
    )
    _prepare_legal_search_rows(db_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )

    encode_started = Event()
    release_encode = Event()

    blocking_encoder = _DirectionalLegalEncoder(revision=0)
    original_encode = blocking_encoder.encode

    def block_query_encode(
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        encode_started.set()
        if not release_encode.wait(timeout=5):
            raise RuntimeError("test timed out waiting to release query encode")
        return original_encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=normalize_embeddings,
        )

    blocking_encoder.encode = block_query_encode

    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=blocking_encoder,
        query_profile=_legal_query_profile(tmp_path),
    )
    results: list[list[object]] = []
    failures: list[BaseException] = []

    def search() -> None:
        try:
            results.append(graph.search_entities("target", top_k=1, min_similarity=0.0))
        except BaseException as exc:  # surfaced in the owning test thread
            failures.append(exc)

    search_thread = Thread(target=search, daemon=True)
    try:
        search_thread.start()
        assert encode_started.wait(timeout=5)
        legal_embedder.build_local_embeddings_and_indexes(
            db_path=db_path,
            output_dir=tmp_path,
            embedding_model="legal-fixture-model",
            embedding_device="cpu",
            encoder=_DirectionalLegalEncoder(revision=1),
            incremental=False,
        )
        release_encode.set()
        search_thread.join(timeout=5)
        assert not search_thread.is_alive()
        assert failures == []
        assert [result.entity_id for result in results[0]] == ["entity-target"]
        with pytest.raises(LegalQueryProfileError, match="query_profile_stale_or_mismatched"):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
    finally:
        release_encode.set()
        search_thread.join(timeout=5)
        graph.close()


def test_previous_rule_generation_is_unsupported_even_with_same_encoder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-target", "target entity")])
    encoder = _DirectionalLegalEncoder(revision=0)
    monkeypatch.setattr(
        legal_embedder, "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION", "policyos.legal.embedding.v1"
    )
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=encoder,
    )
    monkeypatch.setattr(
        legal_embedder, "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION", "policyos.legal.embedding.v2"
    )
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=encoder,
        query_profile=_legal_query_profile(tmp_path),
    )
    try:
        with pytest.raises(LegalQueryProfileError, match="query_rule_version_mismatch"):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
    finally:
        graph.close()


def test_openai_label_does_not_authorize_query_vectors_and_hybrid_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[object] = []

    class _UnexpectedOpenAIClient:
        def __init__(self, **_kwargs: object) -> None:
            calls.append("constructed")

    monkeypatch.setitem(
        sys.modules,
        "openai",
        types.SimpleNamespace(OpenAI=_UnexpectedOpenAIClient),
    )
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[])
    _prepare_legal_search_rows(db_path)
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        openai_api_key="fixture-key",
        embedding_model="legal-fixture-model",
    )
    try:
        assert graph.search_entities("target", top_k=1, min_similarity=0.0) == []
        assert graph.query_profile_error is not None
        assert graph.query_profile_error.code == "query_encoder_assets_unavailable"
        results = graph.hybrid_search(
            "target",
            top_k=1,
            trust_tier=None,
            include_candidates=True,
        )
        assert [result.fact_id for result in results] == ["fact-target"]
    finally:
        graph.close()
    assert calls == []


@pytest.mark.parametrize("profile_case", ["missing", "foreign_table", "duplicate", "wrong_model", "malformed"])
def test_actual_query_refuses_missing_unpaired_or_wrong_requested_profile_before_encode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    profile_case: str,
) -> None:
    import hnswlib

    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-target", "target entity")])
    _prepare_legal_search_rows(db_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )
    profiles = _legal_query_profile(tmp_path)
    entity = next(p for p in profiles if p.basis_kind == "legal_lex_entities_embedding")
    requested: tuple[LegalQueryProfile, ...] | None
    if profile_case == "missing":
        requested = None
        expected_code = "query_profile_unavailable"
    elif profile_case == "foreign_table":
        requested = tuple(p for p in profiles if p.basis_kind != entity.basis_kind)
        expected_code = "query_profile_unpaired"
    elif profile_case == "duplicate":
        requested = (entity, entity)
        expected_code = "query_profile_unpaired"
    elif profile_case == "malformed":
        requested = cast("tuple[LegalQueryProfile, ...]", list(profiles))
        expected_code = "query_profile_malformed"
    else:
        wrong_inventory = json.loads(entity.inventory_bytes)
        wrong_inventory["embedding_model"] = "wrong-same-dimension-model"
        requested = (
            LegalQueryProfile(
                basis_kind=entity.basis_kind,
                generation_id=entity.generation_id,
                inventory_bytes=json.dumps(
                    wrong_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8"),
            ),
        )
        expected_code = "query_profile_stale_or_mismatched"

    knn_calls = 0
    original_knn = hnswlib.Index.knn_query

    def record_knn(index: object, *args: object, **kwargs: object) -> object:
        nonlocal knn_calls
        knn_calls += 1
        return original_knn(index, *args, **kwargs)

    monkeypatch.setattr(hnswlib.Index, "knn_query", record_knn)
    encoder = _DirectionalLegalEncoder(revision=0)
    graph = LegalKnowledgeGraph(
        db_path, tmp_path, query_encoder=encoder, query_profile=requested
    )
    try:
        with pytest.raises(LegalQueryProfileError, match=expected_code):
            graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert graph.query_profile_error is not None
        assert graph.query_profile_error.code == expected_code
        assert encoder.encoded_texts == []
        assert knn_calls == 0
    finally:
        graph.close()


def test_same_assets_new_generation_requires_fresh_request_intent_and_fresh_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import hnswlib

    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(
        db_path,
        entities=[("entity-target", "target entity"), ("entity-decoy", "decoy entity")],
    )
    _prepare_legal_search_rows(db_path)
    producer = _DirectionalLegalEncoder(revision=0)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=producer,
    )
    previous = _legal_query_profile(tmp_path)
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=producer,
    )
    current = _legal_query_profile(tmp_path)
    previous_entity = next(p for p in previous if p.basis_kind == "legal_lex_entities_embedding")
    current_entity = next(p for p in current if p.basis_kind == previous_entity.basis_kind)
    assert previous_entity.generation_id != current_entity.generation_id
    assert json.loads(previous_entity.inventory_bytes)["basis"] == json.loads(
        current_entity.inventory_bytes
    )["basis"]

    knn_calls = 0
    original_knn = hnswlib.Index.knn_query

    def record_knn(index: object, *args: object, **kwargs: object) -> object:
        nonlocal knn_calls
        knn_calls += 1
        return original_knn(index, *args, **kwargs)

    monkeypatch.setattr(hnswlib.Index, "knn_query", record_knn)
    encoder = _DirectionalLegalEncoder(revision=0)
    stale = LegalKnowledgeGraph(
        db_path, tmp_path, query_encoder=encoder, query_profile=previous
    )
    try:
        with pytest.raises(LegalQueryProfileError, match="query_profile_stale_or_mismatched"):
            stale.search_entities("target", top_k=1, min_similarity=0.0)
        assert encoder.encoded_texts == []
        assert knn_calls == 0

        # Remove only request/selected-generation pairing. Keep the real local
        # encoder, asset checks, normalization, membership, and native HNSW.
        original_gate = stale._store._require_query_profile
        monkeypatch.setattr(
            LegalKnowledgeStore,
            "_require_query_profile",
            staticmethod(lambda *_args, **_kwargs: None),
        )
        assert [
            result.entity_id
            for result in stale.search_entities("target", top_k=1, min_similarity=0.0)
        ] == ["entity-target"]
        assert encoder.encoded_texts == ["target"]
        assert knn_calls == 1
        monkeypatch.setattr(
            LegalKnowledgeStore, "_require_query_profile", staticmethod(original_gate)
        )
        with pytest.raises(LegalQueryProfileError, match="query_profile_stale_or_mismatched"):
            stale.search_entities("target", top_k=1, min_similarity=0.0)
        assert knn_calls == 1
    finally:
        stale.close()

    fresh = LegalKnowledgeGraph(
        db_path, tmp_path, query_encoder=_DirectionalLegalEncoder(revision=0), query_profile=current
    )
    try:
        assert [
            result.entity_id
            for result in fresh.search_entities("target", top_k=1, min_similarity=0.0)
        ] == ["entity-target"]
        assert knn_calls == 2
    finally:
        fresh.close()


def test_request_snapshot_does_not_alias_selected_generation_inventory(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_lex_db(db_path, entities=[("entity-target", "target entity")])
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        embedding_model="legal-fixture-model",
        embedding_device="cpu",
        encoder=_DirectionalLegalEncoder(revision=0),
    )
    generation = resolve_embedding_generation(
        tmp_path / ".legal_embedding_generations" / "lex_entity_embeddings"
    )
    assert generation is not None
    requested = LegalQueryProfile.from_generation(generation)
    frozen_bytes = requested.inventory_bytes
    generation.inventory["embedding_model"] = "mutated-caller-dict"
    assert requested.inventory_bytes == frozen_bytes
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=_DirectionalLegalEncoder(revision=0),
        query_profile=(requested,),
    )
    try:
        assert [
            result.entity_id
            for result in graph.search_entities("target", top_k=1, min_similarity=0.0)
        ] == ["entity-target"]
    finally:
        graph.close()


@pytest.mark.parametrize(
    "basis_kind,generation_id,inventory",
    [
        ("legal_lex_entities_embedding", "generation", bytearray(b"{}")),
        ("", "generation", b"{}"),
        ("legal_lex_entities_embedding", "", b"{}"),
        ("legal_lex_entities_embedding", "generation", "{}"),
    ],
)
def test_raw_query_profile_cannot_carry_mutable_or_malformed_snapshot(
    basis_kind: str,
    generation_id: str,
    inventory: object,
) -> None:
    with pytest.raises(LegalQueryProfileError, match="query_profile_malformed"):
        LegalQueryProfile(
            basis_kind=basis_kind,
            generation_id=generation_id,
            inventory_bytes=cast("bytes", inventory),
        )
