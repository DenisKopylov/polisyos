"""EMB-03 witnesses for content-bound legal embedding reuse.

These tests intentionally exercise the legal batch owner rather than inspecting
sidecar keys in isolation.  A legal embedding may be reused only when the
projected text, encoder profile, projection rule, and current membership are
all bound to the same generation.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import ClassVar

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.legal.batch import embedder as legal_embedder

pytestmark = pytest.mark.unit


class _FakeSentenceTransformer:
    """Deterministic encoder whose model name controls revision and dimension."""

    instances: ClassVar[list[_FakeSentenceTransformer]] = []

    def __init__(self, model_name: str, device: str | None = None, **_kwargs: object) -> None:
        self.model_name = model_name
        self.device = device
        self.dimension = 5 if model_name.endswith("-dim5") else 4
        type(self).instances.append(self)

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
        rows: list[np.ndarray] = []
        revision_offset = 11.0 if self.model_name.startswith("model-b") else 0.0
        for text in texts:
            base = float((sum(map(ord, str(text))) % 17) + 1) + revision_offset
            vector = np.arange(base, base + self.dimension, dtype=np.float32)
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
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


def _entity_ids(output_dir: Path) -> list[str]:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return [str(value) for value in payload["ids"]]


def _entity_vectors(output_dir: Path) -> np.ndarray:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return np.asarray(payload["vectors"], dtype=np.float32).copy()


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
