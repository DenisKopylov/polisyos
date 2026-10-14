"""EMB-03 witnesses for content-bound legal embedding reuse.

These tests intentionally exercise the legal batch owner rather than inspecting
sidecar keys in isolation.  A legal embedding may be reused only when the
projected text, encoder profile, projection rule, and current membership are
all bound to the same generation.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import types
from collections.abc import Callable, Sequence
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import ClassVar, cast

import duckdb
import numpy as np
import pytest

from polisyos.core.contracts.control import (
    LegalQueryGenerationIntentV1,
    LexSearchRequest,
)
from polisyos.data_forge.domains.legal import embedding_projection as legal_projection
from polisyos.data_forge.domains.legal import runtime_material as legal_runtime_material
from polisyos.data_forge.domains.legal.batch import embedder as legal_embedder
from polisyos.data_forge.kernel.embeddings import (
    _generator_rule_version,
    derive_encoder_identity,
    resolve_embedding_generation,
)
from polisyos.data_forge.read_api import legal as legal_read_api
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.knowledge.store import (
    LegalKnowledgeStore,
    LegalQueryProfile,
    LegalQueryProfileError,
)
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import (
    LegalQueryEncoderProvider,
    LegalQueryEncoderProviderError,
    RuntimeContainerOverrides,
)
from polisyos.runtime.http.services.control.lex_pipeline import LexPipelineMixin

pytestmark = pytest.mark.unit


class _FakeSentenceTransformer:
    """Deterministic encoder whose model name controls revision and dimension."""

    instances: ClassVar[list[_FakeSentenceTransformer]] = []
    tokenizer_revision: ClassVar[int] = 0

    def __init__(self, model_name: str, device: str | None = None, **_kwargs: object) -> None:
        self.model_name = model_name
        self.device = device
        self.dimension = 5 if model_name.endswith("-dim5") else 4
        self.config = {"model_name": model_name, "dimension": self.dimension}
        self.tokenizer = _FakeTokenizer(type(self).tokenizer_revision)
        self.encoded_texts: list[str] = []
        type(self).instances.append(self)

    def state_dict(self) -> dict[str, np.ndarray]:
        revision = sum(ord(char) for char in self.model_name)
        return {"encoder.weight": np.asarray([self.dimension, revision], dtype=np.float32)}

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
        revision_offset = 11.0 if self.model_name.startswith("model-b") else 0.0
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
    """Directional fake with a configurable output dimension."""

    def __init__(
        self,
        *,
        revision: int = 0,
        device: str = "cpu",
        dimension: int = 4,
    ) -> None:
        self.revision = revision
        self.device = device
        self.model_name = "directional-legal"
        self.dimension = dimension
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
        rows: list[np.ndarray] = []
        for text in texts:
            axis = 0 if "target" in str(text).lower() else 1
            vector = np.zeros(self.dimension, dtype=np.float32)
            vector[axis] = 1.0
            if normalize_embeddings:
                vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.vstack(rows)


def _install_fake_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSentenceTransformer.instances.clear()
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


def _entity_ids(output_dir: Path) -> list[str]:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return [str(value) for value in payload["ids"]]


def _entity_vectors(output_dir: Path) -> np.ndarray:
    with np.load(output_dir / "lex_entity_embeddings.npz", allow_pickle=True) as payload:
        return np.asarray(payload["vectors"], dtype=np.float32).copy()


def _generation_selectors(output_dir: Path) -> list[Path]:
    return sorted(output_dir.rglob("embedding_generation.json"))


def _prepare_legal_vector_db(
    db_path: Path,
    *,
    entities: list[tuple[str, str]] | None = None,
) -> None:
    _prepare_lex_db(
        db_path,
        entities=entities or [("entity-target", "recorded target")],
    )
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "fact-1",
                "Cabinet",
                "Кабмін",
                "sets",
                "budget",
                "бюджет",
                "Cabinet sets the budget",
                "norm",
                "set",
                "budget_setting",
                "",
                "",
                "",
                "",
                "стаття 1",
            ],
        )
        con.execute(
            "INSERT INTO lex_provisions VALUES (?, ?)",
            ["provision-1", "Budget submissions shall be published."],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _build_legal_vectors(
    db_path: Path,
    output_dir: Path,
    encoder: object,
    *,
    embedding_model: str = "model-a",
) -> None:
    legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=output_dir,
        embedding_model=embedding_model,
        embedding_device="cpu",
        encoder=encoder,
    )


def _legal_query_profiles(output_dir: Path) -> tuple[LegalQueryProfile, ...]:
    profiles: list[LegalQueryProfile] = []
    for npz_name, hnsw_name in (
        ("lex_entity_embeddings", "lex_entity_index"),
        ("lex_fact_embeddings", "lex_fact_index"),
        ("lex_provision_embeddings", "lex_provision_index"),
    ):
        reference = resolve_embedding_generation(
            output_dir / ".legal_embedding_generations" / npz_name,
            legacy_embeddings_path=output_dir / f"{npz_name}.npz",
            legacy_index_path=output_dir / f"{hnsw_name}.hnsw",
        )
        assert reference is not None
        profiles.append(LegalQueryProfile.from_generation(reference))
    return tuple(profiles)


def _search_legal_table(graph: LegalKnowledgeGraph, table: str) -> list[object]:
    if table == "entities":
        return graph.search_entities("target", top_k=1, min_similarity=0.0)
    if table == "facts":
        return graph.search_facts("budget", top_k=1, min_similarity=0.0, trust_tier=None)
    if table == "provisions":
        return graph.search_provisions("budget", top_k=1, min_similarity=0.0)
    raise AssertionError(f"unexpected legal table: {table}")


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
    monkeypatch.setattr(
        legal_embedder,
        "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION",
        "policyos.legal.embedding.v2",
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


@pytest.mark.parametrize(
    ("project", "row", "expected"),
    [
        (
            legal_projection.entity_embedding_text,
            ("Budget Office", "Бюджетне управління", "agency", "Finance; Budget", "Мінфін"),
            "ENTITY\nen: Budget Office\nuk: Бюджетне управління\ntype: agency\n"
            "aliases: Finance; Budget; Мінфін",
        ),
        (
            legal_projection.fact_embedding_text,
            (
                "Cabinet",
                "Кабмін",
                "approves",
                "budget",
                "бюджет",
                "Cabinet approves the budget",
                "norm",
                "approve",
                "approval",
                "after review",
                "emergency exception",
                "submit a report",
                '{"amount": 3}',
                "Article 7",
            ),
            "FACT\nnorm_type: approval\naction: approve\n"
            "spo: Cabinet (Кабмін) approves budget (бюджет)\n"
            "fact_en: Cabinet approves the budget\ncondition_uk: after review\n"
            "exception_uk: emergency exception\nprocedure_uk: submit a report\n"
            'thresholds: {"amount": 3}\nquote_uk: Article 7',
        ),
        (
            legal_projection.provision_embedding_text,
            ("Budget submissions shall be published.",),
            "Budget submissions shall be published.",
        ),
    ],
)
def test_canonical_legal_embedding_projections(
    project: Callable[[Sequence[object]], str], row: Sequence[object], expected: str
) -> None:
    assert project(row) == expected


@pytest.mark.parametrize(
    ("project", "row"),
    [
        (legal_projection.entity_embedding_text, ("too", "short")),
        (legal_projection.fact_embedding_text, ("too", "short")),
        (legal_projection.provision_embedding_text, ()),
    ],
)
def test_canonical_legal_embedding_projection_rejects_incomplete_rows(
    project: Callable[[Sequence[object]], str], row: Sequence[object]
) -> None:
    with pytest.raises(ValueError):
        project(row)


def test_missing_and_mixed_intent_refuse_all_vector_tables_before_encode(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(db_path)
    producer = _FakeSentenceTransformer("model-a", device="cpu")
    _build_legal_vectors(db_path, tmp_path, producer)
    first_profiles = _legal_query_profiles(tmp_path)

    missing_encoder = _FakeSentenceTransformer("model-a", device="cpu")
    missing = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=missing_encoder,
        query_profile=None,
    )
    try:
        for table in ("entities", "facts", "provisions"):
            with pytest.raises(LegalQueryProfileError) as caught:
                _search_legal_table(missing, table)
            assert caught.value.code == "query_profile_unavailable"
            assert missing.query_profile_error is caught.value
        assert missing_encoder.encoded_texts == []
    finally:
        missing.close()

    _build_legal_vectors(db_path, tmp_path, producer)
    current_profiles = _legal_query_profiles(tmp_path)
    query_encoder = _FakeSentenceTransformer("model-a", device="cpu")
    for requested_table in ("entities", "facts", "provisions"):
        current_profile = next(
            profile
            for profile in current_profiles
            if profile.basis_kind == f"legal_lex_{requested_table}_embedding"
        )
        previous_profile = next(
            profile
            for profile in first_profiles
            if profile.basis_kind == current_profile.basis_kind
        )
        mixed_profile = LegalQueryProfile(
            basis_kind=current_profile.basis_kind,
            generation_id=current_profile.generation_id,
            inventory_bytes=previous_profile.inventory_bytes,
        )
        requested_profiles = tuple(
            mixed_profile if profile.basis_kind == current_profile.basis_kind else profile
            for profile in current_profiles
        )
        graph = LegalKnowledgeGraph(
            db_path,
            tmp_path,
            query_encoder=query_encoder,
            query_profile=requested_profiles,
        )
        try:
            with pytest.raises(LegalQueryProfileError) as caught:
                _search_legal_table(graph, requested_table)
            assert caught.value.code == "query_profile_stale_or_mismatched"
            assert graph.query_profile_error is caught.value
        finally:
            graph.close()
    assert query_encoder.encoded_texts == []

    # A valid current intent reaches the common downstream gate for every
    # vector family; the inventory/profile markers alone cannot authorize encode.
    current_encoder = _FakeSentenceTransformer("model-a", device="cpu")
    current = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=current_encoder,
        query_profile=current_profiles,
    )
    try:
        for table in ("entities", "facts", "provisions"):
            with pytest.raises(LegalQueryProfileError) as caught:
                _search_legal_table(current, table)
            assert caught.value.code == "query_encoder_runtime_material_not_established"
            assert current.query_profile_error is caught.value
        assert current_encoder.encoded_texts == []
    finally:
        current.close()


class _CountingIndex:
    def __init__(self, index: object) -> None:
        self._index = index
        self.knn_calls = 0

    def knn_query(self, *args: object, **kwargs: object) -> object:
        self.knn_calls += 1
        return self._index.knn_query(*args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._index, name)


def test_fresh_intent_still_requires_runtime_material_before_vector_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(db_path)
    producer = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    previous_profiles = _legal_query_profiles(tmp_path)

    # A second run with the same corpus and assets still selects a new generation.
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    current_profiles = _legal_query_profiles(tmp_path)
    stale_encoder = _DirectionalLegalEncoder()
    selected = resolve_embedding_generation(
        tmp_path / ".legal_embedding_generations" / "lex_entity_embeddings"
    )
    assert selected is not None
    assert selected.inventory["basis"]["generator_rule_version"] == _generator_rule_version(
        projection_rule_version=legal_projection.LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
        embedding_model=producer.model_name,
        embedding_device="cpu",
        embedding_dimension=producer.dimension,
        encoder_identity=derive_encoder_identity(stale_encoder),
    )
    stale = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=stale_encoder,
        query_profile=previous_profiles,
    )
    try:
        with pytest.raises(LegalQueryProfileError) as caught:
            stale.search_entities("target", top_k=1, min_similarity=0.0)
        assert caught.value.code == "query_profile_stale_or_mismatched"
        assert stale_encoder.encoded_texts == []

        counted_index = _CountingIndex(stale._store._entity_index)
        stale._store._entity_index = counted_index
        with monkeypatch.context() as patcher:
            # Remove only the runtime-material gate to show the independent
            # request-intent gate still rejects an old selected generation.
            patcher.setattr(
                LegalKnowledgeStore,
                "_require_query_runtime_material_binding",
                staticmethod(lambda *_args, **_kwargs: None),
            )
            with pytest.raises(LegalQueryProfileError) as stale_after_runtime_gate_removed:
                stale.search_entities("target", top_k=1, min_similarity=0.0)
        assert stale_after_runtime_gate_removed.value.code == "query_profile_stale_or_mismatched"
        assert stale_encoder.encoded_texts == []
        assert counted_index.knn_calls == 0
    finally:
        stale.close()

    fresh_encoder = _DirectionalLegalEncoder()
    fresh = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=fresh_encoder,
        query_profile=current_profiles,
    )
    try:
        with monkeypatch.context() as patcher:
            # The current generation and request profile are a controlled
            # positive for the pre-existing reader path; this bypass is a
            # remove-the-property witness, not a production runtime binding.
            patcher.setattr(
                LegalKnowledgeStore,
                "_require_query_runtime_material_binding",
                staticmethod(lambda *_args, **_kwargs: None),
            )
            results = fresh.search_entities("target", top_k=1, min_similarity=0.0)
        assert [result.entity_id for result in results] == ["entity-target"]
        assert fresh_encoder.encoded_texts == ["target"]
    finally:
        fresh.close()


def test_producer_selected_intent_reaches_fresh_served_reader_with_typed_fallback(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_legal_vector_db(db_path)
    with duckdb.connect(str(db_path)) as con:
        con.execute("ALTER TABLE lex_facts ADD COLUMN trust_tier VARCHAR")
        con.execute("UPDATE lex_facts SET trust_tier = 'grounded_fact'")
    producer = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    producer_profiles = _legal_query_profiles(tmp_path)
    request_intent = tuple(
        LegalQueryGenerationIntentV1(
            basis_kind=profile.basis_kind,
            generation_id=profile.generation_id,
            inventory_json=profile.inventory_bytes.decode("utf-8"),
        )
        for profile in producer_profiles
    )

    response = LexPipelineMixin().search_lex_graph(
        LexSearchRequest(
            query="budget",
            top_k=3,
            output_dir=str(tmp_path),
            query_generation_intent=request_intent,
        ),
        request_id="req-fresh-legal-reader",
    )

    assert response.search_mode == "text"
    assert response.vector_refusal_code == "query_encoder_assets_unavailable"
    assert [result.fact_id for result in response.results] == ["fact-1"]


def test_producer_generation_reaches_native_http_with_typed_runtime_material_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        from fastapi.testclient import TestClient
    except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
        pytest.skip("fastapi test client is not installed")
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())

    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_legal_vector_db(db_path)
    with duckdb.connect(str(db_path)) as con:
        con.execute("ALTER TABLE lex_facts ADD COLUMN trust_tier VARCHAR")
        con.execute("UPDATE lex_facts SET trust_tier = 'grounded_fact'")

    # The real Legal producer persists the selected generation. A second object
    # has identical assets but a replacement callable whose execution must be blocked.
    producer = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    producer_encode_history = tuple(producer.encoded_texts)
    query_encoder = _DirectionalLegalEncoder()
    assert derive_encoder_identity(producer) == derive_encoder_identity(query_encoder)
    decoy_calls: list[str] = []

    def _decoy_encode(
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar, normalize_embeddings
        decoy_calls.extend(texts)
        return np.tile(np.asarray([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    query_encoder.encode = _decoy_encode  # type: ignore[method-assign]
    provider = LegalQueryEncoderProvider(encoder=query_encoder)
    counted_indexes: list[_CountingIndex] = []
    original_load_fact_index = LegalKnowledgeStore._load_fact_index

    def _load_counted_fact_index(
        store: LegalKnowledgeStore,
    ) -> tuple[object, list[str], object]:
        index, fact_ids, generation = original_load_fact_index(store)
        counted = _CountingIndex(index)
        store._fact_index = counted
        counted_indexes.append(counted)
        return counted, fact_ids, generation

    monkeypatch.setattr(LegalKnowledgeStore, "_load_fact_index", _load_counted_fact_index)
    app = create_runtime_api_app(
        cas_root=tmp_path / "runtime-cas",
        allow_fixture_identity=True,
        enable_security_middlewares=False,
        container_overrides=RuntimeContainerOverrides(legal_query_encoder_provider=provider),
    )

    with TestClient(app) as client:
        profile_response = client.get(
            "/api/v1/control/lex/search-profile",
            params={"output_dir": str(tmp_path)},
        )
        assert profile_response.status_code == 200, profile_response.text
        profile = profile_response.json()
        assert profile["status"] == "available"
        intent = profile["query_generation_intent"]
        assert len(intent) == 1
        payload = {
            "query": "budget",
            "top_k": 3,
            "output_dir": str(tmp_path),
            "query_generation_intent": intent,
        }
        response = client.post("/api/v1/control/lex/search", json=payload)

        stale_intent = [dict(item) for item in intent]
        original_inventory = stale_intent[0]["inventory_json"]
        generation_id = stale_intent[0]["generation_id"]
        stale_intent[0]["generation_id"] = "e" * 32 if generation_id == "f" * 32 else "f" * 32
        assert stale_intent[0]["inventory_json"] == original_inventory
        stale_response = client.post(
            "/api/v1/control/lex/search",
            json={**payload, "query_generation_intent": stale_intent},
        )

        query_encoder.revision += 1
        changed_encoder_response = client.post("/api/v1/control/lex/search", json=payload)
        query_encoder.revision -= 1
        empty_intent_response = client.post(
            "/api/v1/control/lex/search",
            json={**payload, "query_generation_intent": []},
        )

        default_app = create_runtime_api_app(
            cas_root=tmp_path / "default-runtime-cas",
            allow_fixture_identity=True,
            enable_security_middlewares=False,
        )
        with TestClient(default_app) as default_client:
            fallback_response = default_client.post("/api/v1/control/lex/search", json=payload)

        # Mutate a projected current member after GET; the same GET intent must
        # produce a membership refusal before the runtime-material refusal.
        with duckdb.connect(str(db_path)) as con:
            con.execute(
                "UPDATE lex_facts SET fact_text = ? WHERE fact_id = ?",
                ["changed current legal text", "fact-1"],
            )
        member_response = client.post("/api/v1/control/lex/search", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["search_mode"] == "text"
    assert body["vector_refusal_code"] == "query_encoder_runtime_material_not_established"
    assert [item["fact_id"] for item in body["results"]] == ["fact-1"]
    assert tuple(producer.encoded_texts) == producer_encode_history
    assert decoy_calls == []
    assert app.state.runtime_container.legal_query_encoder_provider is provider

    assert stale_response.status_code == 200, stale_response.text
    stale_body = stale_response.json()
    assert stale_body["search_mode"] == "text"
    assert stale_body["vector_refusal_code"] == "query_profile_stale_or_mismatched"
    assert [item["fact_id"] for item in stale_body["results"]] == ["fact-1"]

    assert changed_encoder_response.status_code == 200, changed_encoder_response.text
    changed_body = changed_encoder_response.json()
    assert changed_body["search_mode"] == "text"
    assert changed_body["vector_refusal_code"] == "encoder_identity_mismatch"
    assert [item["fact_id"] for item in changed_body["results"]] == ["fact-1"]

    assert empty_intent_response.status_code == 200, empty_intent_response.text
    empty_body = empty_intent_response.json()
    assert empty_body["search_mode"] == "text"
    assert empty_body["vector_refusal_code"] == "query_profile_malformed"
    assert [item["fact_id"] for item in empty_body["results"]] == ["fact-1"]

    assert default_app.state.runtime_container.legal_query_encoder_provider is None
    assert fallback_response.status_code == 200, fallback_response.text
    fallback_body = fallback_response.json()
    assert fallback_body["search_mode"] == "text"
    assert fallback_body["vector_refusal_code"] == "query_encoder_assets_unavailable"
    assert [item["fact_id"] for item in fallback_body["results"]] == ["fact-1"]

    assert member_response.status_code == 200, member_response.text
    member_body = member_response.json()
    assert member_body["search_mode"] == "text"
    assert member_body["vector_refusal_code"] == "selected_generation_membership_mismatch"
    assert [item["fact_id"] for item in member_body["results"]] == ["fact-1"]
    assert decoy_calls == []
    assert all(index.knn_calls == 0 for index in counted_indexes)


def test_current_generation_refuses_changed_projected_members_before_encode(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(db_path)
    _build_legal_vectors(
        db_path, tmp_path, _DirectionalLegalEncoder(), embedding_model="directional-legal"
    )
    profiles = _legal_query_profiles(tmp_path)
    _replace_entity_name(db_path, "entity-target", "different current text")

    query_encoder = _DirectionalLegalEncoder()
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=query_encoder,
        query_profile=profiles,
    )
    try:
        with pytest.raises(LegalQueryProfileError) as caught:
            graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert caught.value.code == "selected_generation_membership_mismatch"
        assert query_encoder.encoded_texts == []
    finally:
        graph.close()


def test_query_encoder_assets_must_match_before_encoding(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(db_path)
    producer = _FakeSentenceTransformer("model-a", device="cpu")
    _build_legal_vectors(db_path, tmp_path, producer)
    query_encoder = _FakeSentenceTransformer("model-b", device="cpu")
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=query_encoder,
        query_profile=_legal_query_profiles(tmp_path),
    )
    try:
        with pytest.raises(LegalQueryProfileError) as caught:
            graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert caught.value.code == "encoder_identity_mismatch"
        assert query_encoder.encoded_texts == []
    finally:
        graph.close()


def test_runtime_and_graph_refuse_same_asset_query_callable_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(
        db_path,
        entities=[("entity-target", "recorded target"), ("entity-decoy", "recorded decoy")],
    )
    producer = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    profiles = _legal_query_profiles(tmp_path)

    swapped = _DirectionalLegalEncoder()

    def _replaced_encode(
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        del batch_size, show_progress_bar, normalize_embeddings
        swapped.encoded_texts.extend(texts)
        return np.tile(np.asarray([[0.0, 1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    swapped.encode = _replaced_encode  # type: ignore[method-assign]
    assert derive_encoder_identity(producer) == derive_encoder_identity(swapped)
    counted_indexes: list[_CountingIndex] = []
    original_load_entity_index = LegalKnowledgeStore._load_entity_index

    def _load_counted_entity_index(
        store: LegalKnowledgeStore,
    ) -> tuple[object, list[str], object]:
        index, entity_ids, generation = original_load_entity_index(store)
        counted = _CountingIndex(index)
        store._entity_index = counted
        counted_indexes.append(counted)
        return counted, entity_ids, generation

    monkeypatch.setattr(LegalKnowledgeStore, "_load_entity_index", _load_counted_entity_index)
    provider = LegalQueryEncoderProvider(encoder=swapped)
    with pytest.raises(LegalQueryEncoderProviderError) as provider_refusal:
        provider.resolve_encoder()
    assert provider_refusal.value.code == "query_encoder_runtime_material_not_established"
    assert swapped.encoded_texts == []

    # Direct graph callers bypass the HTTP provider. The same source-owned store
    # gate must still block every raw encoder before its executable method runs.
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=swapped,
        query_profile=profiles,
    )
    try:
        with pytest.raises(LegalQueryProfileError) as graph_refusal:
            graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert graph_refusal.value.code == "query_encoder_runtime_material_not_established"
        assert swapped.encoded_texts == []
        assert all(index.knn_calls == 0 for index in counted_indexes)

        with monkeypatch.context() as patcher:
            # Remove the property gate while preserving generation/profile
            # markers: the actual decoy callable then wins, proving the gate is
            # behavioral and distinguishes the same-assets sibling case.
            patcher.setattr(
                LegalKnowledgeStore,
                "_require_query_runtime_material_binding",
                staticmethod(lambda *_args, **_kwargs: None),
            )
            results = graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert [result.entity_id for result in results] == ["entity-decoy"]
        assert swapped.encoded_texts == ["target"]
        assert any(index.knn_calls > 0 for index in counted_indexes)
    finally:
        graph.close()


@pytest.mark.parametrize("operator", ["between", "in"])
@pytest.mark.parametrize("lower_bound", [0.0, 1e-5])
@pytest.mark.parametrize("candidate_value", [-1.0, 0.0, 1e-5, 2.0, 5.0, 6.0])
def test_reopened_threshold_consumer_retains_numeric_scalar(
    tmp_path: Path,
    operator: str,
    lower_bound: float,
    candidate_value: float,
) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "CREATE TABLE lex_facts (fact_id VARCHAR, confidence DOUBLE, trust_tier VARCHAR)"
        )
        con.execute("INSERT INTO lex_facts VALUES ('fact-zero', 1.0, 'normative_fact')")
        con.execute(
            "CREATE TABLE lex_rule_thresholds ("
            "threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR, operator VARCHAR, "
            "value_decimal DOUBLE, value_text VARCHAR, unit VARCHAR, applies_to VARCHAR)"
        )
        con.execute(
            "INSERT INTO lex_rule_thresholds VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "threshold-zero",
                "fact-zero",
                "distance",
                operator,
                lower_bound,
                "5",
                "km",
                "firms",
            ],
        )

    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        result = store.evaluate_rule_threshold(
            threshold_id="threshold-zero",
            candidate_value=candidate_value,
            candidate_unit="km",
            applies_to="firms",
        )
    finally:
        store.close()

    admitted = (
        lower_bound <= candidate_value <= 5.0
        if operator == "between"
        else candidate_value in {lower_bound, 5.0}
    )
    assert result.status == ("admitted" if admitted else "blocked")
    assert result.reason == ("threshold_satisfied" if admitted else "threshold_violated")
    assert result.normalized_candidate_value == candidate_value
    assert result.normalized_threshold_value == lower_bound
    assert result.canonical_unit == "km"
    assert result.threshold_id == "threshold-zero"
    assert result.fact_id == "fact-zero"


def test_owned_runtime_resolution_waits_for_fresh_intent_and_members(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(db_path)
    tables = ("entities", "facts", "provisions")
    producer = _DirectionalLegalEncoder(dimension=1024)
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    stale_profiles = _legal_query_profiles(tmp_path)
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)
    wrong_model_profiles = _legal_query_profiles(tmp_path)

    owner = legal_read_api.LegalRuntimeMaterialOwner(
        cache_root=tmp_path / "unopened-local-cache",
        manifest_path=tmp_path / "unopened-manifest",
    )
    resolution_attempts: list[str] = []

    def _forbidden_resolution() -> object:
        resolution_attempts.append("called")
        raise AssertionError("unadmitted candidates must be rejected before owner resolution")

    monkeypatch.setattr(owner, "resolve_encoder", _forbidden_resolution)

    # A stale GET intent remains distinguishable before model identity or owner availability.
    stale_graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_profile=stale_profiles,
        query_runtime_material_owner=owner,
    )
    try:
        for table in tables:
            with pytest.raises(LegalQueryProfileError) as stale:
                _search_legal_table(stale_graph, table)
            assert stale.value.code == "query_profile_stale_or_mismatched"
    finally:
        stale_graph.close()
    assert resolution_attempts == []

    # The ordinary generation path records a different model identity. Do not
    # relabel this as merely unestablished owner material: mismatch is exact.
    wrong_model_graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_profile=wrong_model_profiles,
        query_runtime_material_owner=owner,
    )
    try:
        for table in tables:
            with pytest.raises(LegalQueryProfileError) as wrong_model:
                _search_legal_table(wrong_model_graph, table)
            assert wrong_model.value.code == "encoder_identity_mismatch"
    finally:
        wrong_model_graph.close()
    assert resolution_attempts == []

    # This generation goes through the ordinary Legal producer with the owner's
    # model-name label and supported dimension, but has no source-issued runtime
    # binding. Candidate metadata alone cannot authorize loading or vector use.
    claimed_owner_label_producer = _DirectionalLegalEncoder(dimension=1024)
    _build_legal_vectors(
        db_path,
        tmp_path,
        claimed_owner_label_producer,
        embedding_model=owner.embedding_model,
    )
    unbound_profiles = _legal_query_profiles(tmp_path)
    runtime_marker = f"{legal_read_api.LEGAL_RUNTIME_MATERIAL_RULE_VERSION}=".encode()
    assert owner.embedding_model.encode() in unbound_profiles[0].inventory_bytes
    assert runtime_marker not in unbound_profiles[0].inventory_bytes
    producer_history = tuple(claimed_owner_label_producer.encoded_texts)

    unbound_graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_profile=unbound_profiles,
        query_runtime_material_owner=owner,
    )
    try:
        for table in tables:
            with pytest.raises(LegalQueryProfileError) as unbound:
                _search_legal_table(unbound_graph, table)
            assert unbound.value.code == "query_encoder_runtime_material_not_established"
    finally:
        unbound_graph.close()
    assert resolution_attempts == []
    assert tuple(claimed_owner_label_producer.encoded_texts) == producer_history

    # Current member drift remains its own refusal for each consumer and still
    # precedes model identity/binding resolution.
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "UPDATE lex_entities SET name_en = ?, name_uk = ? WHERE entity_id = ?",
            ["changed current entity", "змінена сутність", "entity-target"],
        )
        con.execute(
            "UPDATE lex_facts SET fact_text = ? WHERE fact_id = ?",
            ["changed current material", "fact-1"],
        )
        con.execute(
            "UPDATE lex_provisions SET provision_text = ? WHERE provision_id = ?",
            ["Changed current provision text.", "provision-1"],
        )
        con.execute("CHECKPOINT")
    member_graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_profile=unbound_profiles,
        query_runtime_material_owner=owner,
    )
    try:
        for table in tables:
            with pytest.raises(LegalQueryProfileError) as changed_member:
                _search_legal_table(member_graph, table)
            assert changed_member.value.code == "selected_generation_membership_mismatch"
    finally:
        member_graph.close()
    assert resolution_attempts == []
    assert tuple(claimed_owner_label_producer.encoded_texts) == producer_history


def test_python_runtime_profile_distinguishes_venv_launch_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    resolved_executable = Path(sys.executable).resolve(strict=True)
    first_launcher = tmp_path / "venv-one" / "bin" / "python"
    second_launcher = tmp_path / "venv-two" / "bin" / "python"
    first_launcher.parent.mkdir(parents=True)
    second_launcher.parent.mkdir(parents=True)
    first_launcher.symlink_to(resolved_executable)
    second_launcher.symlink_to(resolved_executable)

    first_profile = legal_runtime_material._python_execution_profile(
        str(first_launcher), require_loaded_runtime_modules=False
    )
    second_profile = legal_runtime_material._python_execution_profile(
        str(second_launcher), require_loaded_runtime_modules=False
    )

    assert first_profile["executable_resolved_path"] == second_profile["executable_resolved_path"]
    assert first_profile["executable_sha256"] == second_profile["executable_sha256"]
    assert (
        first_profile["executable_invocation_path"] != second_profile["executable_invocation_path"]
    )
    assert first_profile != second_profile
    first_prefixes = first_profile["prefixes"]
    first_site_packages = first_profile["site_packages"]
    assert isinstance(first_prefixes, dict)
    assert isinstance(first_site_packages, dict)
    assert first_prefixes["prefix"] == sys.prefix
    assert first_profile["sys_path"]
    assert first_site_packages["global"]
    with monkeypatch.context() as profile_patch:
        profile_patch.setattr(sys, "prefix", str(tmp_path / "alternate-prefix"))
        alternate_prefix_profile = legal_runtime_material._python_execution_profile(
            str(first_launcher), require_loaded_runtime_modules=False
        )
    alternate_prefixes = alternate_prefix_profile["prefixes"]
    assert isinstance(alternate_prefixes, dict)
    assert alternate_prefixes["prefix"] != first_prefixes["prefix"]
    assert alternate_prefix_profile != first_profile

    alternate_site = tmp_path / "alternate-site-packages"
    with monkeypatch.context() as profile_patch:
        profile_patch.setattr(
            legal_runtime_material.site,
            "getsitepackages",
            lambda: [str(alternate_site)],
        )
        alternate_site_profile = legal_runtime_material._python_execution_profile(
            str(first_launcher), require_loaded_runtime_modules=False
        )
    alternate_site_packages = alternate_site_profile["site_packages"]
    assert isinstance(alternate_site_packages, dict)
    assert alternate_site_packages["global"][0]["invocation_path"] == str(alternate_site)
    assert alternate_site_profile != first_profile


def test_runtime_profile_bootstrap_stabilizes_modules_and_refuses_later_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    try:
        for distribution_name in legal_runtime_material._RUNTIME_ROOT_DISTRIBUTIONS:
            importlib_metadata.distribution(distribution_name)
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("the owner-controlled runtime profile is not installed")

    for module_name in legal_runtime_material._REQUIRED_RUNTIME_PROFILE_MODULES:
        importlib.import_module(module_name)
    if "hnswlib" in sys.modules:
        monkeypatch.delitem(sys.modules, "hnswlib")
    unprimed_profile = legal_runtime_material._loaded_runtime_module_profile()
    assert unprimed_profile["hnswlib"]["state"] == "not_loaded"
    unprimed_digest = legal_runtime_material._installed_runtime_digest()

    legal_runtime_material._load_runtime_profile_modules()
    warmed_profile = legal_runtime_material._loaded_runtime_module_profile()
    assert tuple(warmed_profile) == legal_runtime_material._RUNTIME_PROFILE_MODULES
    assert all(
        warmed_profile[name]["state"] != "not_loaded"
        for name in legal_runtime_material._RUNTIME_PROFILE_MODULES
    )
    assert warmed_profile["hnswlib"]["state"] == "loaded_file"
    warmed_digest = legal_runtime_material._installed_runtime_digest()
    assert warmed_digest != unprimed_digest
    hnswlib_module = importlib.import_module("hnswlib")
    hnswlib_path = Path(str(hnswlib_module.__file__)).resolve()
    assert warmed_profile["hnswlib"]["resolved_path"] == str(hnswlib_path)
    assert (
        warmed_profile["hnswlib"]["sha256"] == hashlib.sha256(hnswlib_path.read_bytes()).hexdigest()
    )
    assert legal_runtime_material._installed_runtime_digest() == warmed_digest

    class _Tokenizer:
        @property
        def special_tokens_map(self) -> dict[str, str]:
            return {}

        def get_vocab(self) -> dict[str, int]:
            return {"token": 0}

        def get_added_vocab(self) -> dict[str, int]:
            return {}

    class _Model:
        def __init__(self) -> None:
            self.device = "cpu"
            self.config: dict[str, object] = {}
            self.training = False
            self.tokenizer = _Tokenizer()
            self.weight = np.zeros((1,), dtype=np.float32)
            self.encode_calls = 0

        def named_parameters(self) -> list[tuple[str, np.ndarray]]:
            return [("weight", self.weight)]

        def named_buffers(self) -> list[tuple[str, np.ndarray]]:
            return []

        def modules(self) -> list[_Model]:
            return [self]

        def get_sentence_embedding_dimension(self) -> int:
            return 1024

        def encode(self, texts: list[str], **_kwargs: object) -> np.ndarray:
            self.encode_calls += 1
            return np.zeros((len(texts), 1024), dtype=np.float32)

    model = _Model()
    asset_identity = derive_encoder_identity(
        model,
        include_live_model_state=True,
        require_zero_copy=True,
    )
    owner = legal_runtime_material.LegalRuntimeMaterialOwner(
        cache_root=tmp_path,
        manifest_path=tmp_path / "manifest.json",
    )
    model_files_digest = "a" * 64
    runtime_digest = legal_runtime_material._installed_runtime_digest()
    source_digest = legal_runtime_material._source_closure_digest()
    bound_encode = model.encode
    encode_fingerprint = legal_runtime_material._encode_method_fingerprint(bound_encode)
    binding_digest = legal_runtime_material._binding_digest(
        model_files_digest=model_files_digest,
        asset_identity=asset_identity,
        runtime_digest=runtime_digest,
        source_digest=source_digest,
        encode_fingerprint=encode_fingerprint,
    )
    handle = legal_runtime_material.LegalRuntimeMaterialHandle(
        owner=owner,
        model=model,
        asset_identity=asset_identity,
        model_files_digest=model_files_digest,
        runtime_digest=runtime_digest,
        source_digest=source_digest,
        encode_fingerprint=encode_fingerprint,
        binding_digest=binding_digest,
        bound_encode=bound_encode,
        _seal=legal_runtime_material._HANDLE_SEAL,
    )
    owner._handles[binding_digest] = handle

    monkeypatch.delitem(sys.modules, "hnswlib")
    with (
        pytest.raises(legal_runtime_material.LegalRuntimeMaterialError) as drift,
        handle.checked_encode_lease(
            expected_binding=binding_digest,
            expected_assets=asset_identity,
        ) as checked_encode,
    ):
        checked_encode(["must not execute"])
    assert drift.value.code == "query_encoder_runtime_material_changed"
    assert model.encode_calls == 0


def test_model_file_inventory_confines_snapshot_and_blob_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    revision = legal_runtime_material.LEGAL_CONTROLLED_MODEL_REVISION
    model_cache_directory = (
        f"models--{legal_runtime_material.LEGAL_CONTROLLED_MODEL_ID.replace('/', '--')}"
    )
    cache_root = tmp_path / "hf-cache"
    model_root = cache_root / model_cache_directory
    snapshot = model_root / "snapshots" / revision
    blobs = model_root / "blobs"
    snapshot.mkdir(parents=True)
    blobs.mkdir(parents=True)

    names = [f"member-{index:02d}.bin" for index in range(9)]
    file_entries: list[dict[str, object]] = []
    contents: dict[str, bytes] = {}
    for name in names:
        content = f"fixture-material:{name}".encode()
        contents[name] = content
        (blobs / name).write_bytes(content)
        (snapshot / name).symlink_to(Path("..") / ".." / "blobs" / name)
        file_entries.append(
            {
                "name": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )

    manifest = {
        "revision": revision,
        "named_file_count": len(file_entries),
        "files": file_entries,
        "logical_bytes": sum(len(content) for content in contents.values()),
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_path = tmp_path / "asset-file-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(
        legal_runtime_material,
        "LEGAL_CONTROLLED_MANIFEST_SHA256",
        hashlib.sha256(manifest_bytes).hexdigest(),
    )

    digest, members = legal_runtime_material._model_file_inventory(
        snapshot=snapshot,
        cache_root=cache_root,
        manifest_path=manifest_path,
    )
    assert len(digest) == 64
    assert [str(member["name"]) for member in members] == sorted(names)
    assert [str(member["sha256"]) for member in members] == [
        hashlib.sha256(contents[name]).hexdigest() for name in sorted(names)
    ]

    outside_snapshot = tmp_path / "outside" / model_cache_directory / "snapshots" / revision
    outside_snapshot.mkdir(parents=True)
    with pytest.raises(legal_runtime_material.LegalRuntimeMaterialError) as outside_refusal:
        legal_runtime_material._model_file_inventory(
            snapshot=outside_snapshot,
            cache_root=cache_root,
            manifest_path=manifest_path,
        )
    assert outside_refusal.value.code == "query_encoder_runtime_material_not_established"

    escaped_cache_root = tmp_path / "escaped-cache"
    escaped_cache_root.mkdir()
    (escaped_cache_root / model_cache_directory).symlink_to(model_root, target_is_directory=True)
    with pytest.raises(legal_runtime_material.LegalRuntimeMaterialError) as cache_refusal:
        legal_runtime_material._model_file_inventory(
            snapshot=snapshot,
            cache_root=escaped_cache_root,
            manifest_path=manifest_path,
        )
    assert cache_refusal.value.code == "query_encoder_runtime_material_not_established"

    escaped_blobs_root = tmp_path / "escaped-blob-cache"
    escaped_model_root = escaped_blobs_root / model_cache_directory
    escaped_snapshot = escaped_model_root / "snapshots" / revision
    external_blobs = tmp_path / "external-blobs"
    escaped_snapshot.mkdir(parents=True)
    external_blobs.mkdir()
    (escaped_model_root / "blobs").symlink_to(external_blobs, target_is_directory=True)
    for name in names:
        (external_blobs / name).write_bytes(contents[name])
        (escaped_snapshot / name).symlink_to(Path("..") / ".." / "blobs" / name)

    with pytest.raises(legal_runtime_material.LegalRuntimeMaterialError) as blobs_refusal:
        legal_runtime_material._model_file_inventory(
            snapshot=escaped_snapshot,
            cache_root=escaped_blobs_root,
            manifest_path=manifest_path,
        )
    assert blobs_refusal.value.code == "query_encoder_runtime_material_not_established"


def test_local_owned_runtime_material_producer_get_post_and_callable_falsifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    try:
        sentence_transformers_version = importlib_metadata.version("sentence-transformers")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("the pinned SentenceTransformers runtime is not installed")
    if sentence_transformers_version != "2.7.0":
        pytest.skip("the controlled witness requires SentenceTransformers 2.7.0")

    repo_root = Path(__file__).resolve().parents[3]
    profile_root = (
        repo_root / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
        "c12-real-encoder-profile"
    )
    cache_root = profile_root / "hf-cache"
    manifest_path = profile_root / "asset-file-manifest.txt"
    if not cache_root.is_dir() or not manifest_path.is_file():
        pytest.skip("the named local-only controlled model inputs are unavailable")

    try:
        from fastapi.testclient import TestClient
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
        pytest.skip("controlled runtime dependencies are not installed")

    encoded_texts: list[str] = []
    encode_batches: list[list[str]] = []
    encoded_models: list[object] = []
    producer_mutation: dict[str, object] = {"armed": True, "mutated": False}
    query_mutation: dict[str, object] = {"armed": False, "mutated": False}
    original_encode = cast("Callable[..., object]", SentenceTransformer.encode)

    def _mutate_first_parameter(model: object) -> tuple[object, float]:
        parameters_method = getattr(model, "parameters", None)
        assert callable(parameters_method)
        parameter = next(iter(parameters_method()))
        first_value = parameter.data.view(-1)[0]
        original_value = float(first_value.item())
        first_value.add_(1)
        return parameter, original_value

    def _restore_first_parameter(parameter: object, original_value: float) -> None:
        parameter.data.view(-1)[0].fill_(original_value)

    def _counted_encode(
        model: object,
        texts: list[str],
        *args: object,
        **kwargs: object,
    ) -> object:
        result = original_encode(model, texts, *args, **kwargs)
        encoded_texts.extend(texts)
        encode_batches.append(list(texts))
        encoded_models.append(model)
        if query_mutation["armed"] is True:
            parameter, original_value = _mutate_first_parameter(model)
            query_mutation["parameter"] = parameter
            query_mutation["original_value"] = original_value
            query_mutation["armed"] = False
            query_mutation["mutated"] = True
        return result

    monkeypatch.setattr(SentenceTransformer, "encode", _counted_encode)
    original_pause = legal_embedder.pause_between_batches

    def _mutate_between_fact_chunks(seconds: float) -> None:
        original_pause(seconds)
        last_batch = encode_batches[-1] if encode_batches else []
        if producer_mutation["armed"] is True and any(
            "Cabinet" in text and "budget" in text for text in last_batch
        ):
            parameter, original_value = _mutate_first_parameter(encoded_models[-1])
            producer_mutation["parameter"] = parameter
            producer_mutation["original_value"] = original_value
            producer_mutation["armed"] = False
            producer_mutation["mutated"] = True

    monkeypatch.setattr(legal_embedder, "pause_between_batches", _mutate_between_fact_chunks)

    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    _prepare_legal_vector_db(db_path)
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "fact-decoy",
                "Municipal council",
                "Міська рада",
                "denies",
                "tax credit",
                "податковий кредит",
                "The council denies the tax credit.",
                "norm",
                "deny",
                "tax_credit_denial",
                "",
                "",
                "",
                "",
                "Article 9",
            ],
        )
        con.executemany(
            "INSERT INTO lex_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                [
                    f"fact-noise-{index:02d}",
                    "Transit office",
                    "Транспортний відділ",
                    "publishes",
                    "rail service notice",
                    "повідомлення про графік поїздів",
                    f"Transit office publishes rail service notice {index}.",
                    "norm",
                    "publish",
                    "transit_notice",
                    "",
                    "",
                    "",
                    "",
                    "Transit rule",
                ]
                for index in range(7)
            ],
        )
        con.execute("ALTER TABLE lex_facts ADD COLUMN trust_tier VARCHAR")
        con.execute("UPDATE lex_facts SET trust_tier = 'grounded_fact'")
        con.execute("CHECKPOINT")

    owner = legal_read_api.LegalRuntimeMaterialOwner(
        cache_root=cache_root,
        manifest_path=manifest_path,
    )
    with pytest.raises(legal_read_api.LegalRuntimeMaterialError) as changed_between_chunks:
        legal_embedder.build_local_embeddings_and_indexes(
            db_path=db_path,
            output_dir=tmp_path,
            runtime_material_owner=owner,
        )
    assert changed_between_chunks.value.code == "query_encoder_runtime_material_changed"
    mutated_parameter = producer_mutation["parameter"]
    original_parameter_value = producer_mutation["original_value"]
    assert mutated_parameter is not None and isinstance(original_parameter_value, float)
    _restore_first_parameter(mutated_parameter, original_parameter_value)
    fact_batches_before_refusal = [
        batch
        for batch in encode_batches
        if any("Cabinet" in text and "budget" in text for text in batch)
    ]
    assert [len(batch) for batch in fact_batches_before_refusal] == [8]
    assert producer_mutation["mutated"] is True
    assert not (
        tmp_path
        / ".legal_embedding_generations"
        / "lex_fact_embeddings"
        / "embedding_generation.json"
    ).exists()
    encoded_texts.clear()
    encode_batches.clear()
    encoded_models.clear()

    stats = legal_embedder.build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=tmp_path,
        runtime_material_owner=owner,
    )
    assert stats.facts_embedded == 9
    handle = owner.resolve_encoder()
    reference = resolve_embedding_generation(
        tmp_path / ".legal_embedding_generations" / "lex_fact_embeddings",
        legacy_embeddings_path=tmp_path / "lex_fact_embeddings.npz",
        legacy_index_path=tmp_path / "lex_fact_index.hnsw",
    )
    assert reference is not None and reference.selected and reference.status == "complete"
    bound_rule = reference.inventory["basis"]["generator_rule_version"]
    assert (
        f"{legal_read_api.LEGAL_RUNTIME_MATERIAL_RULE_VERSION}={handle.binding_digest}"
        in bound_rule
    )
    identity_before_swap = derive_encoder_identity(
        handle,
        include_live_model_state=True,
        require_zero_copy=True,
    )

    decoy_vector: np.ndarray
    with np.load(reference.embeddings_path, allow_pickle=True) as payload:
        fact_ids = tuple(str(item) for item in payload["ids"].tolist())
        vectors = np.asarray(payload["vectors"], dtype=np.float32)
    decoy_vector = vectors[fact_ids.index("fact-decoy")].copy()

    original_load_entity_index = LegalKnowledgeStore._load_entity_index
    original_load_fact_index = LegalKnowledgeStore._load_fact_index
    original_load_provision_index = LegalKnowledgeStore._load_provision_index
    counted_indexes: list[_CountingIndex] = []

    def _track_index(index: object) -> _CountingIndex:
        counted = index if isinstance(index, _CountingIndex) else _CountingIndex(index)
        if all(existing is not counted for existing in counted_indexes):
            counted_indexes.append(counted)
        return counted

    def _total_knn_calls() -> int:
        return sum(index.knn_calls for index in counted_indexes)

    def _counted_entity_index(
        store: LegalKnowledgeStore,
    ) -> tuple[object, list[str], object]:
        index, entity_ids, generation = original_load_entity_index(store)
        counted = _track_index(index)
        store._entity_index = counted
        return counted, entity_ids, generation

    def _counted_fact_index(
        store: LegalKnowledgeStore,
    ) -> tuple[object, list[str], object]:
        index, fact_ids, generation = original_load_fact_index(store)
        counted = _track_index(index)
        store._fact_index = counted
        return counted, fact_ids, generation

    def _counted_provision_index(
        store: LegalKnowledgeStore,
    ) -> tuple[object, list[str], object]:
        index, provision_ids, generation = original_load_provision_index(store)
        counted = _track_index(index)
        store._provision_index = counted
        return counted, provision_ids, generation

    monkeypatch.setattr(LegalKnowledgeStore, "_load_entity_index", _counted_entity_index)
    monkeypatch.setattr(LegalKnowledgeStore, "_load_fact_index", _counted_fact_index)
    monkeypatch.setattr(LegalKnowledgeStore, "_load_provision_index", _counted_provision_index)

    provider = LegalQueryEncoderProvider(runtime_material_owner=owner)
    app = create_runtime_api_app(
        cas_root=tmp_path / "runtime-cas",
        allow_fixture_identity=True,
        enable_security_middlewares=False,
        container_overrides=RuntimeContainerOverrides(legal_query_encoder_provider=provider),
    )
    query = legal_projection.fact_embedding_text(
        (
            "Cabinet",
            "Кабмін",
            "sets",
            "budget",
            "бюджет",
            "Cabinet sets the budget",
            "norm",
            "set",
            "budget_setting",
            "",
            "",
            "",
            "",
            "стаття 1",
        )
    )

    with TestClient(app) as client:
        get_response = client.get(
            "/api/v1/control/lex/search-profile",
            params={"output_dir": str(tmp_path)},
        )
        assert get_response.status_code == 200, get_response.text
        profile_body = get_response.json()
        assert profile_body["status"] == "available"
        intent = profile_body["query_generation_intent"]
        payload = {
            "query": query,
            "top_k": 1,
            "output_dir": str(tmp_path),
            "query_generation_intent": intent,
        }
        positive_knn_calls_before = _total_knn_calls()
        post_response = client.post("/api/v1/control/lex/search", json=payload)

        assert post_response.status_code == 200, post_response.text
        positive_body = post_response.json()
        assert positive_body["search_mode"] == "vector"
        assert positive_body["vector_refusal_code"] is None
        assert [row["fact_id"] for row in positive_body["results"]] == ["fact-1"]
        assert _total_knn_calls() - positive_knn_calls_before == 1

        # The owner uses its captured identity only as the expected binding.
        # A live mutation must be rejected by the lease before encode/HNSW.
        parameter, original_value = _mutate_first_parameter(handle._model)
        encoded_before_live_mutation = len(encoded_texts)
        knn_calls_before_live_mutation = _total_knn_calls()
        live_mutation_response = client.post("/api/v1/control/lex/search", json=payload)
        assert live_mutation_response.status_code == 200, live_mutation_response.text
        live_mutation_body = live_mutation_response.json()
        assert live_mutation_body["search_mode"] == "text"
        assert live_mutation_body["vector_refusal_code"] == (
            "query_encoder_runtime_material_changed"
        )
        assert len(encoded_texts) == encoded_before_live_mutation
        assert _total_knn_calls() == knn_calls_before_live_mutation
        _restore_first_parameter(parameter, original_value)

        # A mutation during encode is caught by the lease's post-call check;
        # its query vector never reaches native HNSW.
        query_mutation["armed"] = True
        encoded_before_postcheck = len(encoded_texts)
        knn_calls_before_postcheck = _total_knn_calls()
        postcheck_response = client.post("/api/v1/control/lex/search", json=payload)
        assert postcheck_response.status_code == 200, postcheck_response.text
        postcheck_body = postcheck_response.json()
        assert postcheck_body["search_mode"] == "text"
        assert postcheck_body["vector_refusal_code"] == ("query_encoder_runtime_material_changed")
        assert query_mutation["mutated"] is True
        assert len(encoded_texts) == encoded_before_postcheck + 1
        assert _total_knn_calls() == knn_calls_before_postcheck
        query_parameter = query_mutation["parameter"]
        query_original_value = query_mutation["original_value"]
        assert query_parameter is not None and isinstance(query_original_value, float)
        _restore_first_parameter(query_parameter, query_original_value)

        profiles = _legal_query_profiles(tmp_path)
        direct_graph = LegalKnowledgeGraph(
            db_path,
            tmp_path,
            query_profile=profiles,
            query_runtime_material_owner=owner,
        )
        try:
            for table in ("entities", "facts", "provisions"):
                knn_calls_before_direct_search = _total_knn_calls()
                assert _search_legal_table(direct_graph, table)
                assert _total_knn_calls() - knn_calls_before_direct_search == 1
        finally:
            direct_graph.close()

        alternate_site = tmp_path / "alternate-site-packages"
        alternate_site.mkdir()
        knn_calls_before_profile_swap = _total_knn_calls()
        encoded_before_profile_swap = len(encoded_texts)
        with monkeypatch.context() as profile_swap:
            profile_swap.setattr(sys, "path", [*sys.path, str(alternate_site)])
            profile_response = client.post("/api/v1/control/lex/search", json=payload)
            assert profile_response.status_code == 200, profile_response.text
            profile_body = profile_response.json()
            assert profile_body["search_mode"] == "text"
            assert profile_body["vector_refusal_code"] == ("query_encoder_runtime_material_changed")
        assert len(encoded_texts) == encoded_before_profile_swap
        assert _total_knn_calls() == knn_calls_before_profile_swap

        decoy_calls: list[str] = []

        def _same_assets_decoy(
            texts: list[str],
            **_kwargs: object,
        ) -> np.ndarray:
            decoy_calls.extend(texts)
            return np.tile(decoy_vector.reshape(1, -1), (len(texts), 1))

        runtime_decoy_calls: list[str] = []

        def _same_assets_runtime_decoy(
            _model: object,
            texts: list[str],
            **_kwargs: object,
        ) -> np.ndarray:
            runtime_decoy_calls.extend(texts)
            return np.tile(decoy_vector.reshape(1, -1), (len(texts), 1))

        knn_calls_before_runtime_swap = _total_knn_calls()
        with monkeypatch.context() as runtime_swap:
            runtime_swap.setattr(type(handle._model), "encode", _same_assets_runtime_decoy)
            assert (
                derive_encoder_identity(
                    handle,
                    include_live_model_state=True,
                    require_zero_copy=True,
                )
                == identity_before_swap
            )
            runtime_response = client.post("/api/v1/control/lex/search", json=payload)
            assert runtime_response.status_code == 200, runtime_response.text
            runtime_body = runtime_response.json()
            assert runtime_body["search_mode"] == "text"
            assert runtime_body["vector_refusal_code"] == ("query_encoder_runtime_material_changed")
        assert runtime_decoy_calls == []
        assert _total_knn_calls() == knn_calls_before_runtime_swap

        handle._model.encode = _same_assets_decoy  # type: ignore[method-assign]
        assert (
            derive_encoder_identity(
                handle,
                include_live_model_state=True,
                require_zero_copy=True,
            )
            == identity_before_swap
        )
        knn_calls_before_callable_swap = _total_knn_calls()
        changed_response = client.post("/api/v1/control/lex/search", json=payload)
        assert changed_response.status_code == 200, changed_response.text
        changed_body = changed_response.json()
        assert changed_body["search_mode"] == "text"
        assert changed_body["vector_refusal_code"] == "query_encoder_runtime_material_changed"
        assert decoy_calls == []
        assert _total_knn_calls() == knn_calls_before_callable_swap

        stale_intent = [dict(item) for item in intent]
        generation_id = stale_intent[0]["generation_id"]
        stale_intent[0]["generation_id"] = "e" * 32 if generation_id != "e" * 32 else "f" * 32
        knn_calls_before_stale_intent = _total_knn_calls()
        stale_response = client.post(
            "/api/v1/control/lex/search",
            json={**payload, "query_generation_intent": stale_intent},
        )
        assert stale_response.status_code == 200, stale_response.text
        stale_body = stale_response.json()
        assert stale_body["vector_refusal_code"] == "query_profile_stale_or_mismatched"
        assert decoy_calls == []
        assert _total_knn_calls() == knn_calls_before_stale_intent

        # The same source-owned gate covers direct entity, fact, and provision
        # vector entrypoints; each call is refused before callable or HNSW use.
        direct_graph = LegalKnowledgeGraph(
            db_path,
            tmp_path,
            query_profile=profiles,
            query_runtime_material_owner=owner,
        )
        try:
            for table in ("entities", "facts", "provisions"):
                knn_calls_before_direct_refusal = _total_knn_calls()
                with pytest.raises(LegalQueryProfileError) as refusal:
                    _search_legal_table(direct_graph, table)
                assert refusal.value.code == "query_encoder_runtime_material_changed"
                assert _total_knn_calls() == knn_calls_before_direct_refusal
        finally:
            direct_graph.close()
        assert decoy_calls == []

        # Remove only the live callable property check while retaining the
        # generation rule token and asset identity. The same-asset decoy then
        # wins, proving the gate distinguishes behavior rather than markers.
        rule_before_removal = reference.inventory["basis"]["generator_rule_version"]
        decoy_calls.clear()
        knn_calls_before_gate_removal = _total_knn_calls()
        with monkeypatch.context() as patcher:
            patcher.setattr(
                legal_read_api.LegalRuntimeMaterialHandle,
                "_assert_live",
                lambda *_args, **_kwargs: None,
            )
            removal_graph = LegalKnowledgeGraph(
                db_path,
                tmp_path,
                query_profile=profiles,
                query_runtime_material_owner=owner,
            )
            try:
                decoy_results = removal_graph.search_facts(
                    query,
                    top_k=1,
                    min_similarity=0.0,
                    trust_tier=None,
                )
            finally:
                removal_graph.close()
        assert reference.inventory["basis"]["generator_rule_version"] == rule_before_removal
        assert [row.fact_id for row in decoy_results] == ["fact-decoy"]
        assert decoy_calls == [query]
        assert _total_knn_calls() - knn_calls_before_gate_removal == 1

        with duckdb.connect(str(db_path)) as con:
            con.execute(
                "UPDATE lex_facts SET fact_text = ? WHERE fact_id = ?",
                ["changed current controlled fact", "fact-1"],
            )
            con.execute("CHECKPOINT")
        knn_calls_before_member_change = _total_knn_calls()
        member_response = client.post("/api/v1/control/lex/search", json=payload)
        assert member_response.status_code == 200, member_response.text
        member_body = member_response.json()
        assert member_body["vector_refusal_code"] == "selected_generation_membership_mismatch"
        assert _total_knn_calls() == knn_calls_before_member_change

    assert app.state.runtime_container.legal_query_encoder_provider is provider
