"""Native reuse boundaries for the controlled_legal_incremental_boundaries_v1 profile.

Only encoder computation is doubled. SQL, persisted basis/inventory, the common
publisher, NPZ/HNSW, and fresh selected readback remain real. These checks do not
qualify owned SentenceTransformers serving or retrieval utility.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pytest

from polisyos.data_forge.domains.legal.batch.embedder import (
    EmbeddingStats,
    build_local_embeddings_and_indexes,
)
from polisyos.data_forge.domains.legal.embedding_projection import (
    LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
)
from polisyos.data_forge.kernel.embeddings import (
    EmbeddingGenerationRef,
    derive_encoder_identity,
    embedding_generation_matches_encoder,
    resolve_embedding_generation,
)
from tests.unit.data_forge.legal_batch.test_embed_local import (
    _FakeSentenceTransformer,
    _FakeTokenizer,
    _prepare_lex_db,
)

_MODEL = "controlled_legal_incremental_boundaries_v1"
_PROJECTIONS = {
    "lex_entity_embeddings": ("legal_lex_entities_embedding", ("e1", "e2")),
    "lex_fact_embeddings": ("legal_lex_facts_embedding", ("f1", "f2")),
    "lex_provision_embeddings": ("legal_lex_provisions_embedding", ("p1", "p2")),
}


class _RevisionTokenizer(_FakeTokenizer):
    def __init__(self) -> None:
        self.revision = 0

    def get_vocab(self) -> dict[str, int]:
        return {**super().get_vocab(), f"revision-{self.revision}": 2}


class _RecordingEncoder(_FakeSentenceTransformer):
    def __init__(self) -> None:
        super().__init__(_MODEL, device="cpu")
        self.tokenizer = _RevisionTokenizer()
        self.batches: list[tuple[str, ...]] = []

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        self.batches.append(tuple(texts))
        return super().encode(texts, batch_size, show_progress_bar, normalize_embeddings)


def _seed(db_path: Path) -> None:
    _prepare_lex_db(db_path)
    with duckdb.connect(str(db_path)) as connection:
        connection.execute(
            "INSERT INTO lex_entities SELECT 'e2', * EXCLUDE (entity_id) FROM lex_entities"
        )
        connection.execute("INSERT INTO lex_facts SELECT 'f2', * EXCLUDE (fact_id) FROM lex_facts")
        connection.execute(
            "INSERT INTO lex_provisions SELECT 'p2', * EXCLUDE (provision_id) FROM lex_provisions"
        )
        connection.execute("CHECKPOINT")


def _build(
    db_path: Path, output: Path, encoder: _RecordingEncoder, *, incremental: bool
) -> EmbeddingStats:
    return build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=output,
        embedding_model=_MODEL,
        embedding_device="cpu",
        embedding_batch_size=2,
        embedding_chunk_size=2,
        incremental=incremental,
        encoder=encoder,
    )


def _counts(stats: EmbeddingStats) -> dict[str, tuple[int, int]]:
    return {
        "lex_entity_embeddings": (stats.entities_embedded, stats.entities_skipped),
        "lex_fact_embeddings": (stats.facts_embedded, stats.facts_skipped),
        "lex_provision_embeddings": (stats.provisions_embedded, stats.provisions_skipped),
    }


def _readback(
    output: Path, encoder: _RecordingEncoder
) -> dict[str, tuple[EmbeddingGenerationRef, np.ndarray]]:
    import hnswlib

    result = {}
    for name, (kind, expected_ids) in _PROJECTIONS.items():
        reference = resolve_embedding_generation(output / ".legal_embedding_generations" / name)
        assert reference is not None and reference.selected and reference.status == "complete"
        assert reference.ids == expected_ids and reference.dimension == 4
        assert reference.inventory["embedding_model"] == _MODEL
        assert embedding_generation_matches_encoder(
            reference,
            encoder=encoder,
            basis_kind=kind,
            projection_rule_version=LEGAL_EMBEDDING_PROJECTION_RULE_VERSION,
            embedding_model=_MODEL,
            embedding_device="cpu",
            embedding_dimension=4,
        )
        with np.load(reference.embeddings_path, allow_pickle=True) as payload:
            assert tuple(payload["ids"].tolist()) == expected_ids
            matrix = payload["vectors"].copy()
        assert matrix.dtype == np.float32 and matrix.shape == (2, 4)
        assert reference.index_path is not None
        index = hnswlib.Index(space="cosine", dim=4)
        index.load_index(str(reference.index_path))
        assert index.get_current_count() == 2 and set(index.get_ids_list()) == {0, 1}
        np.testing.assert_allclose(index.get_items([0, 1]), matrix, rtol=0, atol=1e-6)
        result[name] = (reference, matrix)
    return result


def _assert_reissued_results(
    previous: dict[str, tuple[EmbeddingGenerationRef, np.ndarray]],
    current: dict[str, tuple[EmbeddingGenerationRef, np.ndarray]],
) -> None:
    for name, (old_reference, old_matrix) in previous.items():
        reference, matrix = current[name]
        assert reference.generation_id != old_reference.generation_id
        assert old_reference.root_dir.is_dir()
        np.testing.assert_array_equal(matrix, old_matrix)


def test_tokenizer_only_drift_recomputes_all_current_projections(tmp_path: Path) -> None:
    db_path = tmp_path / "legal.duckdb"
    _seed(db_path)
    encoder = _RecordingEncoder()
    assert set(_counts(_build(db_path, tmp_path, encoder, incremental=True)).values()) == {(2, 0)}
    encoder.batches.clear()
    assert set(_counts(_build(db_path, tmp_path, encoder, incremental=True)).values()) == {(0, 2)}
    assert encoder.batches == []
    previous = _readback(tmp_path, encoder)
    weights = {name: value.copy() for name, value in encoder.state_dict().items()}
    identity = derive_encoder_identity(encoder)
    encoder.tokenizer.revision = 1
    assert derive_encoder_identity(encoder) != identity
    assert encoder.config == {"model_name": _MODEL, "dimension": 4}
    for name, value in encoder.state_dict().items():
        np.testing.assert_array_equal(value, weights[name])
    stats = _build(db_path, tmp_path, encoder, incremental=True)
    assert set(_counts(stats).values()) == {(2, 0)}
    assert [len(batch) for batch in encoder.batches] == [2, 2, 2]
    _assert_reissued_results(previous, _readback(tmp_path, encoder))


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _corrupt_actual_basis_with_coherent_hashes(reference: EmbeddingGenerationRef) -> None:
    assert reference.basis_path is not None
    assert reference.inventory_path is not None
    assert reference.selector_path is not None
    basis: dict[str, Any] = json.loads(reference.basis_path.read_bytes())
    basis["members"] = "not-a-member-list"
    basis["basis_digest"] = (
        "sha256:"
        + hashlib.sha256(
            _json_bytes({key: value for key, value in basis.items() if key != "basis_digest"})
        ).hexdigest()
    )
    reference.basis_path.write_bytes(_json_bytes(basis))
    inventory = json.loads(reference.inventory_path.read_bytes())
    inventory["basis"] = basis
    inventory["files"]["basis"]["sha256"] = hashlib.sha256(
        reference.basis_path.read_bytes()
    ).hexdigest()
    inventory["files"]["basis"]["size"] = reference.basis_path.stat().st_size
    reference.inventory_path.write_bytes(_json_bytes(inventory))
    selector = json.loads(reference.selector_path.read_bytes())
    selector["inventory_sha256"] = hashlib.sha256(reference.inventory_path.read_bytes()).hexdigest()
    reference.selector_path.write_bytes(_json_bytes(selector))


@pytest.mark.parametrize("projection", tuple(_PROJECTIONS))
def test_malformed_bound_basis_recomputes_only_affected_projection(
    tmp_path: Path, projection: str
) -> None:
    db_path = tmp_path / "legal.duckdb"
    _seed(db_path)
    encoder = _RecordingEncoder()
    _build(db_path, tmp_path, encoder, incremental=True)
    previous = _readback(tmp_path, encoder)
    reference, _matrix = previous[projection]
    assert reference.selector_path is not None
    _corrupt_actual_basis_with_coherent_hashes(reference)
    assert resolve_embedding_generation(reference.selector_path.parent) is None
    encoder.batches.clear()
    stats = _build(db_path, tmp_path, encoder, incremental=True)
    assert _counts(stats) == {
        name: ((2, 0) if name == projection else (0, 2)) for name in _PROJECTIONS
    }
    assert [len(batch) for batch in encoder.batches] == [2]
    _assert_reissued_results(previous, _readback(tmp_path, encoder))


def test_incremental_false_recomputes_valid_cached_projections(tmp_path: Path) -> None:
    db_path = tmp_path / "legal.duckdb"
    _seed(db_path)
    encoder = _RecordingEncoder()
    _build(db_path, tmp_path, encoder, incremental=True)
    encoder.batches.clear()
    assert set(_counts(_build(db_path, tmp_path, encoder, incremental=True)).values()) == {(0, 2)}
    assert encoder.batches == []
    previous = _readback(tmp_path, encoder)
    identity = derive_encoder_identity(encoder)
    stats = _build(db_path, tmp_path, encoder, incremental=False)
    assert derive_encoder_identity(encoder) == identity
    assert set(_counts(stats).values()) == {(2, 0)}
    assert [len(batch) for batch in encoder.batches] == [2, 2, 2]
    _assert_reissued_results(previous, _readback(tmp_path, encoder))
