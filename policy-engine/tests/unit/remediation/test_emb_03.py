"""EMB-03 witnesses for content-bound legal embedding reuse.

These tests intentionally exercise the legal batch owner rather than inspecting
sidecar keys in isolation.  A legal embedding may be reused only when the
projected text, encoder profile, projection rule, and current membership are
all bound to the same generation.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import ClassVar

import duckdb
import numpy as np
import pytest

from polisyos.core.contracts.control import (
    LegalQueryGenerationIntentV1,
    LexSearchRequest,
)
from polisyos.data_forge.domains.legal import embedding_projection as legal_projection
from polisyos.data_forge.domains.legal.batch import embedder as legal_embedder
from polisyos.data_forge.kernel.embeddings import (
    _generator_rule_version,
    derive_encoder_identity,
    resolve_embedding_generation,
)
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.knowledge.store import (
    LegalKnowledgeStore,
    LegalQueryProfile,
    LegalQueryProfileError,
)
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import (
    LegalQueryEncoderProvider,
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
    """Same-dimensional fixture that gives target and decoy separate axes."""

    def __init__(self, *, revision: int = 0, device: str = "cpu") -> None:
        self.revision = revision
        self.device = device
        self.model_name = "directional-legal"
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


class _CountingIndex:
    def __init__(self, index: object) -> None:
        self._index = index
        self.knn_calls = 0

    def knn_query(self, *args: object, **kwargs: object) -> object:
        self.knn_calls += 1
        return self._index.knn_query(*args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._index, name)


def test_same_assets_new_generation_requires_fresh_intent_and_fresh_reader(
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
            patcher.setattr(
                LegalKnowledgeStore,
                "_require_query_profile",
                staticmethod(lambda *_args, **_kwargs: None),
            )
            # Removing only the request gate leaves the producer-built matrix,
            # live encoder checks, and native HNSW query in the exercised path.
            unguarded_results = stale.search_entities("target", top_k=1, min_similarity=0.0)
        assert unguarded_results
        assert stale_encoder.encoded_texts == ["target"]
        assert counted_index.knn_calls == 1
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


def test_producer_generation_reaches_native_http_with_typed_vector_modes(
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

    # This exact loaded encoder produces every persisted generation and is
    # composed into the runtime-owned query provider; the request supplies only
    # immutable selected-generation intent.
    encoder = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, encoder, embedding_model=encoder.model_name)
    profiles = _legal_query_profiles(tmp_path)
    request_intent = tuple(
        LegalQueryGenerationIntentV1(
            basis_kind=profile.basis_kind,
            generation_id=profile.generation_id,
            inventory_json=profile.inventory_bytes.decode("utf-8"),
        )
        for profile in profiles
    )
    provider = LegalQueryEncoderProvider(encoder=encoder)
    app = create_runtime_api_app(
        cas_root=tmp_path / "runtime-cas",
        allow_fixture_identity=True,
        enable_security_middlewares=False,
        container_overrides=RuntimeContainerOverrides(
            legal_query_encoder_provider=provider,
        ),
    )
    payload = {
        "query": "budget",
        "top_k": 3,
        "output_dir": str(tmp_path),
        "query_generation_intent": [item.model_dump(mode="json") for item in request_intent],
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/lex/search",
            json=payload,
        )
        empty_intent_response = client.post(
            "/api/v1/control/lex/search",
            json={**payload, "query_generation_intent": []},
        )
        encoder.revision += 1
        changed_encoder_response = client.post("/api/v1/control/lex/search", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["search_mode"] == "vector"
    assert body["vector_refusal_code"] is None
    assert [item["fact_id"] for item in body["results"]] == ["fact-1"]
    assert encoder.encoded_texts[-1] == "budget"
    assert app.state.runtime_container.legal_query_encoder_provider is provider
    assert empty_intent_response.status_code == 200, empty_intent_response.text
    empty_intent_body = empty_intent_response.json()
    assert empty_intent_body["search_mode"] == "text"
    assert empty_intent_body["vector_refusal_code"] == "query_profile_malformed"
    assert [item["fact_id"] for item in empty_intent_body["results"]] == ["fact-1"]
    assert changed_encoder_response.status_code == 200, changed_encoder_response.text
    changed_body = changed_encoder_response.json()
    assert changed_body["search_mode"] == "text"
    assert changed_body["vector_refusal_code"] == "query_encoder_assets_changed"
    assert [item["fact_id"] for item in changed_body["results"]] == ["fact-1"]

    default_app = create_runtime_api_app(
        cas_root=tmp_path / "default-runtime-cas",
        allow_fixture_identity=True,
        enable_security_middlewares=False,
    )
    with TestClient(default_app) as client:
        fallback_response = client.post("/api/v1/control/lex/search", json=payload)

    assert fallback_response.status_code == 200, fallback_response.text
    fallback_body = fallback_response.json()
    assert default_app.state.runtime_container.legal_query_encoder_provider is None
    assert fallback_body["search_mode"] == "text"
    assert fallback_body["vector_refusal_code"] == "query_encoder_assets_unavailable"
    assert [item["fact_id"] for item in fallback_body["results"]] == ["fact-1"]


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


def test_runtime_asset_provider_cannot_detect_same_asset_query_callable_swap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lex.duckdb"
    _prepare_legal_vector_db(
        db_path,
        entities=[("entity-target", "recorded target"), ("entity-decoy", "recorded decoy")],
    )
    producer = _DirectionalLegalEncoder()
    _build_legal_vectors(db_path, tmp_path, producer, embedding_model=producer.model_name)

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
    provider = LegalQueryEncoderProvider(encoder=swapped)
    # The provider recomputes loaded assets, but those assets do not bind the
    # executable behavior of a replaced method. This is the declared residual.
    assert provider.resolve_encoder() is swapped
    graph = LegalKnowledgeGraph(
        db_path,
        tmp_path,
        query_encoder=provider.resolve_encoder(),
        query_profile=_legal_query_profiles(tmp_path),
    )
    try:
        results = graph.search_entities("target", top_k=1, min_similarity=0.0)
        assert [result.entity_id for result in results] == ["entity-decoy"]
        assert swapped.encoded_texts == ["target"]
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
