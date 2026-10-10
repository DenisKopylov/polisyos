from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from polisyos.data_forge.kernel.embeddings import (
    EmbeddingGenerationRef,
    _build_embedding_generation_from_vectors,
    build_embedding_generation,
    derive_encoder_identity,
    embedding_generation_manifest,
    embedding_generation_matches_encoder,
    hnsw_index_matches_vectors,
    resolve_embedding_generation,
)
from polisyos.data_forge.kernel.io.generation_basis import (
    GenerationIdentity,
    generation_basis_matches_members,
)

_PAD_TOKEN_VALUE = chr(60) + "pad" + chr(62)


class _Tokenizer:
    def __init__(self) -> None:
        self.vocabulary = {"[UNK]": 0, "policy": 1}
        self.special_tokens_map = {"unk_token": "[UNK]"}
        self.model_max_length = 128
        self.padding_side = "right"
        self.truncation_side = "right"
        self.pad_token = _PAD_TOKEN_VALUE
        self.pad_token_id = 1
        self.pad_token_type_id = 0
        self.backend_tokenizer = _BackendTokenizer()

    def get_vocab(self) -> dict[str, int]:
        return dict(self.vocabulary)


class _BackendTokenizer:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.raw_json: str | None = None
        self.payload = (
            payload
            if payload is not None
            else {
                "version": "1.0",
                "truncation": None,
                "padding": None,
                "added_tokens": [],
                "normalizer": {"type": "Lowercase"},
                "pre_tokenizer": {"type": "Whitespace"},
                "post_processor": None,
                "decoder": None,
                "model": {"type": "WordLevel"},
            }
        )

    @classmethod
    def from_str(cls, raw: str) -> _BackendTokenizer:
        return cls(json.loads(raw))

    @property
    def padding(self) -> object:
        value = self.payload["padding"]
        if not isinstance(value, dict):
            return value
        return {
            "direction": str(value["direction"]).lower(),
            "length": None,
            "pad_id": value["pad_id"],
            "pad_to_multiple_of": value["pad_to_multiple_of"],
            "pad_token": value["pad_token"],
            "pad_type_id": value["pad_type_id"],
        }

    @property
    def truncation(self) -> object:
        value = self.payload["truncation"]
        if not isinstance(value, dict):
            return value
        return {
            "direction": str(value["direction"]).lower(),
            "max_length": value["max_length"],
            "strategy": str(value["strategy"]).replace("LongestFirst", "longest_first"),
            "stride": value["stride"],
        }

    def to_str(self) -> str:
        if self.raw_json is not None:
            return self.raw_json
        return json.dumps(self.payload, separators=(",", ":"))

    def no_padding(self) -> None:
        self.payload["padding"] = None

    def no_truncation(self) -> None:
        self.payload["truncation"] = None

    def apply_sentence_transformer_request(self, *, max_length: int) -> None:
        self.payload["padding"] = {
            "direction": "Right",
            "pad_id": 1,
            "pad_to_multiple_of": None,
            "pad_token": _PAD_TOKEN_VALUE,
            "pad_type_id": 0,
            "strategy": "BatchLongest",
        }
        self.payload["truncation"] = {
            "direction": "Right",
            "max_length": max_length,
            "strategy": "LongestFirst",
            "stride": 0,
        }


class _Encoder:
    instances: ClassVar[list[_Encoder]] = []

    def __init__(self) -> None:
        self.weight = np.asarray([1.0, 0.0], dtype=np.float32)
        self.tokenizer = _Tokenizer()
        self.config = {"hidden_size": 2, "layer_norm_eps": 1e-5}
        self.max_seq_length = 128
        type(self).instances.append(self)

    def state_dict(self) -> dict[str, np.ndarray]:
        return {"encoder.weight": self.weight.copy()}

    def modules(self) -> tuple[_Encoder, ...]:
        return (self,)

    def get_config_dict(self) -> dict[str, object]:
        return dict(self.config)

    def encode(self, texts: list[str], **_kwargs: object) -> np.ndarray:
        self.tokenizer.backend_tokenizer.apply_sentence_transformer_request(
            max_length=self.max_seq_length
        )
        vector = self.weight.astype(np.float32)
        return np.vstack([vector for _text in texts])


def _make_hnsw(vectors: np.ndarray, labels: list[int] | None = None) -> object:
    import hnswlib

    matrix = np.asarray(vectors, dtype=np.float32)
    index = hnswlib.Index(space="cosine", dim=matrix.shape[1])
    index.init_index(max_elements=matrix.shape[0])
    actual_labels = labels if labels is not None else list(range(matrix.shape[0]))
    index.add_items(matrix, np.asarray(actual_labels, dtype=np.int64))
    return index


def test_encoder_identity_tracks_live_weights_and_tokenizer_assets() -> None:
    encoder = _Encoder()
    first = derive_encoder_identity(encoder)

    encoder.weight[0] = 2.0
    changed_weights = derive_encoder_identity(encoder)
    encoder.tokenizer.vocabulary["benefit"] = 2
    changed_tokenizer = derive_encoder_identity(encoder)
    encoder.max_seq_length += 1
    changed_sequence_length = derive_encoder_identity(encoder)
    encoder.tokenizer.backend_tokenizer.payload["normalizer"] = {"type": "NFKC"}
    changed_normalizer = derive_encoder_identity(encoder)

    assert first != changed_weights
    assert changed_weights != changed_tokenizer
    assert changed_tokenizer != changed_sequence_length
    assert changed_sequence_length != changed_normalizer


def test_generation_persists_identity_of_encoder_that_produced_vectors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    encoder = _Encoder()
    _Encoder.instances.clear()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=lambda *_args, **_kwargs: encoder),
    )

    first_identity = derive_encoder_identity(encoder)
    build_embedding_generation(
        rows=(("member-1", "policy text"),),
        index_dir=tmp_path,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
    )
    first = resolve_embedding_generation(tmp_path)
    assert first is not None
    first_basis = first.inventory["basis"]
    assert isinstance(first_basis, dict)
    first_rule = str(first_basis["generator_rule_version"])
    with np.load(first.embeddings_path, allow_pickle=True) as payload:
        first_vectors = np.asarray(payload["vectors"], dtype=np.float32)

    encoder.weight[:] = np.asarray([0.0, 1.0], dtype=np.float32)
    second_identity = derive_encoder_identity(encoder)
    build_embedding_generation(
        rows=(("member-1", "policy text"),),
        index_dir=tmp_path,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
    )
    second = resolve_embedding_generation(tmp_path)
    assert second is not None
    second_basis = second.inventory["basis"]
    assert isinstance(second_basis, dict)
    second_rule = str(second_basis["generator_rule_version"])
    with np.load(second.embeddings_path, allow_pickle=True) as payload:
        second_vectors = np.asarray(payload["vectors"], dtype=np.float32)

    assert first_rule.endswith(f"|encoder={first_identity.content_identity}")
    assert second_rule.endswith(f"|encoder={second_identity.content_identity}")
    assert first_rule != second_rule
    assert not np.allclose(first_vectors, second_vectors)
    manifest = embedding_generation_manifest(tmp_path)
    assert manifest is not None
    assert manifest[0]["encoder_identity"] == second_identity.content_identity


def test_generation_uses_injected_encoder_and_derives_its_identity(
    tmp_path: Path,
) -> None:
    encoder = _Encoder()
    expected_identity = derive_encoder_identity(encoder)
    initial_backend_json = encoder.tokenizer.backend_tokenizer.to_str()

    build_embedding_generation(
        rows=(("member-1", "policy text"),),
        index_dir=tmp_path,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
        encoder=encoder,
    )

    generation = resolve_embedding_generation(tmp_path)
    assert generation is not None
    basis = generation.inventory["basis"]
    assert isinstance(basis, dict)
    assert str(basis["generator_rule_version"]).endswith(
        f"|encoder={expected_identity.content_identity}"
    )
    assert encoder.tokenizer.backend_tokenizer.to_str() != initial_backend_json
    assert derive_encoder_identity(encoder) == expected_identity
    with np.load(generation.embeddings_path, allow_pickle=True) as payload:
        vectors = np.asarray(payload["vectors"], dtype=np.float32)
    np.testing.assert_array_equal(vectors, np.asarray([[1.0, 0.0]], dtype=np.float32))


def test_backend_request_state_is_normalized_without_mutating_assets() -> None:
    encoder = _Encoder()
    initial_identity = derive_encoder_identity(encoder)
    encoder.encode(["policy text"])
    backend = encoder.tokenizer.backend_tokenizer
    raw_json = backend.to_str()
    identity = derive_encoder_identity(encoder)

    assert identity == initial_identity
    assert backend.padding == {
        "direction": "right",
        "length": None,
        "pad_id": 1,
        "pad_to_multiple_of": None,
        "pad_token": _PAD_TOKEN_VALUE,
        "pad_type_id": 0,
    }
    assert backend.truncation == {
        "direction": "right",
        "max_length": encoder.max_seq_length,
        "strategy": "longest_first",
        "stride": 0,
    }
    serialized = json.loads(raw_json)
    assert serialized["padding"]["strategy"] == "BatchLongest"
    assert "length" not in serialized["padding"]
    assert serialized["truncation"]["strategy"] == "LongestFirst"
    assert backend.to_str() == raw_json
    assert derive_encoder_identity(encoder) == identity

    mismatched_serialization = json.loads(raw_json)
    mismatched_serialization["padding"]["direction"] = "Left"
    backend.raw_json = json.dumps(mismatched_serialization, separators=(",", ":"))
    live_padding = backend.padding
    assert isinstance(live_padding, dict)
    assert live_padding["direction"] == "right"
    assert derive_encoder_identity(encoder) != identity

    backend.raw_json = None
    backend.payload["padding"]["direction"] = "Left"
    assert derive_encoder_identity(encoder) != identity

    backend.apply_sentence_transformer_request(max_length=encoder.max_seq_length)
    encoder.encode(["a longer text with a different token sequence"])
    assert derive_encoder_identity(encoder) == identity

    backend.apply_sentence_transformer_request(max_length=encoder.max_seq_length - 1)
    assert derive_encoder_identity(encoder) != identity


def test_present_malformed_backend_json_fails_closed() -> None:
    encoder = _Encoder()
    encoder.tokenizer.backend_tokenizer.raw_json = '{"padding":'

    with pytest.raises(ValueError, match="backend JSON is malformed"):
        derive_encoder_identity(encoder)


def test_unsupported_encoder_publishes_unbound_and_cannot_match(
    tmp_path: Path,
) -> None:
    encoder = types.SimpleNamespace(
        encode=lambda texts, **_kwargs: np.tile(
            np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1)
        )
    )
    build_embedding_generation(
        rows=(("member-1", "policy text"),),
        index_dir=tmp_path,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
        basis_kind="legal_entity_embedding",
        projection_rule_version="policyos.legal.embedding.v1",
        encoder=encoder,
    )
    generation = resolve_embedding_generation(tmp_path)
    assert generation is not None
    basis = generation.inventory["basis"]
    assert isinstance(basis, dict)
    assert str(basis["generator_rule_version"]).endswith("|encoder=unbound")
    assert not embedding_generation_matches_encoder(
        generation,
        encoder=_Encoder(),
        basis_kind="legal_entity_embedding",
        projection_rule_version="policyos.legal.embedding.v1",
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
    )


def test_precomputed_generation_requires_identity_from_live_encoder(tmp_path: Path) -> None:
    encoder = _Encoder()
    identity = derive_encoder_identity(encoder)
    rows = (("member-1", "policy text"),)
    vectors = np.asarray([[1.0, 0.0]], dtype=np.float32)
    options = {
        "rows": rows,
        "vectors": vectors,
        "embedding_model": "fixture-label",
        "embedding_device": "cpu",
        "embedding_dimension": 2,
        "basis_kind": "legal_entity_embedding",
        "projection_rule_version": "policyos.legal.embedding.v1",
    }

    with pytest.raises(ValueError, match="requires the live encoder object"):
        _build_embedding_generation_from_vectors(
            index_dir=tmp_path / "identity-only",
            encoder_identity=GenerationIdentity.from_bytes(b"caller label"),
            **options,
        )
    with pytest.raises(ValueError, match="does not match the live encoder"):
        _build_embedding_generation_from_vectors(
            index_dir=tmp_path / "mismatched",
            encoder=encoder,
            encoder_identity=GenerationIdentity.from_bytes(b"caller label"),
            **options,
        )

    _build_embedding_generation_from_vectors(
        index_dir=tmp_path / "bound",
        encoder=encoder,
        encoder_identity=identity,
        **options,
    )
    generation = resolve_embedding_generation(tmp_path / "bound")
    assert generation is not None
    basis = generation.inventory["basis"]
    assert isinstance(basis, dict)
    assert str(basis["generator_rule_version"]).endswith(f"|encoder={identity.content_identity}")


def test_generation_matcher_recomputes_encoder_and_effective_intent(
    tmp_path: Path,
) -> None:
    encoder = _Encoder()
    generation_dir = tmp_path / "complete"
    build_embedding_generation(
        rows=(("member-1", "policy text"),),
        index_dir=generation_dir,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
        basis_kind="catalog_dataset_embedding",
        projection_rule_version="policyos.catalog_dataset_embedding_projection.v1",
        encoder=encoder,
    )
    generation = resolve_embedding_generation(generation_dir)
    assert generation is not None

    expected = {
        "basis_kind": "catalog_dataset_embedding",
        "projection_rule_version": "policyos.catalog_dataset_embedding_projection.v1",
        "embedding_model": "fixture-label",
        "embedding_device": "cpu",
        "embedding_dimension": 2,
    }
    assert embedding_generation_matches_encoder(generation, encoder=encoder, **expected)
    assert not embedding_generation_matches_encoder(
        generation, encoder=encoder, **{**expected, "embedding_model": "different-label"}
    )

    encoder.weight[0] = 3.0
    assert not embedding_generation_matches_encoder(generation, encoder=encoder, **expected)

    empty_dir = tmp_path / "empty"
    build_embedding_generation(
        rows=(),
        index_dir=empty_dir,
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
        basis_kind="catalog_dataset_embedding",
        projection_rule_version="policyos.catalog_dataset_embedding_projection.v1",
    )
    empty_generation = resolve_embedding_generation(empty_dir)
    assert empty_generation is not None
    assert empty_generation.status == "empty_generation"
    assert not embedding_generation_matches_encoder(empty_generation, encoder=encoder, **expected)


def test_legal_read_api_exports_shared_encoder_helpers() -> None:
    from polisyos.data_forge.read_api import legal

    assert legal.EmbeddingGenerationRef is EmbeddingGenerationRef
    assert legal.GenerationIdentity is GenerationIdentity
    assert legal.resolve_embedding_generation is resolve_embedding_generation
    assert legal.derive_encoder_identity is derive_encoder_identity
    assert legal.hnsw_index_matches_vectors is hnsw_index_matches_vectors
    assert legal.embedding_generation_matches_encoder is embedding_generation_matches_encoder
    assert legal.generation_basis_matches_members is generation_basis_matches_members
    identity = GenerationIdentity.from_bytes(b"fixture encoder")
    assert legal.legal_embedding_generator_rule_version(
        projection_rule_version="policyos.legal.embedding.v1",
        embedding_model="fixture-label",
        embedding_device="cpu",
        embedding_dimension=2,
        encoder_identity=identity,
    ) == (
        "policyos.legal.embedding.v1|model=fixture-label|device=cpu|dimension=2"
        f"|encoder={identity.content_identity}"
    )


def test_encoder_identity_does_not_bind_replaced_encode_behavior() -> None:
    encoder = _Encoder()
    original_identity = derive_encoder_identity(encoder)
    original_vectors = encoder.encode(["policy text"])

    encoder.encode = lambda texts, **_kwargs: np.tile(
        np.asarray([[0.0, 1.0]], dtype=np.float32), (len(texts), 1)
    )

    assert derive_encoder_identity(encoder) == original_identity
    assert not np.array_equal(encoder.encode(["policy text"]), original_vectors)


def test_hnsw_index_matches_real_stored_vectors_and_rejects_divergence() -> None:
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    assert hnsw_index_matches_vectors(_make_hnsw(vectors), vectors)
    assert not hnsw_index_matches_vectors(
        _make_hnsw(vectors), np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32)
    )
    assert not hnsw_index_matches_vectors(_make_hnsw(vectors, [1, 0]), vectors)
    assert not hnsw_index_matches_vectors(
        _make_hnsw(vectors), np.asarray([[np.nan, 0.0], [0.0, 1.0]], dtype=np.float32)
    )


def test_legal_projection_contract_is_available_through_read_api() -> None:
    from polisyos.data_forge.read_api import legal

    assert legal.LEGAL_EMBEDDING_PROJECTION_RULE_VERSION == "policyos.legal.embedding.v1"
    assert legal.entity_embedding_text(("Name", "Назва", "concept", "", "")) == (
        "ENTITY\nen: Name\nuk: Назва\ntype: concept"
    )
    assert legal.fact_embedding_text(("subject",) * 14).startswith("FACT\n")
    assert legal.provision_embedding_text(("section text",)) == "section text"
