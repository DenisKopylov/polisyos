"""Shared encode/index mechanics and generation publication for embeddings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np

from polisyos.data_forge.kernel.io.atomic import atomic_commit_path, atomic_write_json
from polisyos.data_forge.kernel.io.generation_basis import (
    GENERATION_BASIS_SCHEMA_VERSION,
    GenerationIdentity,
    build_generation_basis,
)
from polisyos.data_forge.kernel.io.hashing import sha256_bytes, sha256_file
from polisyos.data_forge.kernel.runtime import pause_between_batches

GENERATION_SELECTOR_FILENAME = "embedding_generation.json"
GENERATION_ROOT_DIRNAME = "embedding_generations"
GENERATION_SELECTOR_SCHEMA_VERSION = "policyos.embedding_selector.v1"
GENERATION_INVENTORY_SCHEMA_VERSION = "policyos.embedding_inventory.v1"
EmbeddingGenerationStatus = Literal["complete", "empty_generation", "legacy"]
_GENERATION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class EmbeddingGenerationRef:
    """Validated paths and identity for one readable embedding generation."""

    generation_id: str
    status: EmbeddingGenerationStatus
    root_dir: Path
    embeddings_path: Path
    index_path: Path | None
    ids_path: Path | None
    basis_path: Path | None
    inventory_path: Path | None
    selector_path: Path | None
    ids: tuple[str, ...]
    dimension: int
    inventory: dict[str, object]
    selected: bool


def build_embedding_index(
    *,
    rows: Sequence[tuple[object, str]],
    embeddings_path: Path,
    index_path: Path,
    embedding_model: str,
    embedding_device: str,
    embedding_dimension: int = 1024,
    embedding_batch_size: int = 32,
    thermal_pause_seconds: float = 0.0,
    encoder: object | None = None,
) -> tuple[int, int]:
    """Encode prepared ``(id, text)`` rows and write the legacy index pair.

    The caller owns row selection, text projection, and output naming.  This
    helper only owns the common encode/index operation and deliberately does
    not publish a generation or update a manifest.
    """
    if not rows:
        return 0, int(embedding_dimension)

    import hnswlib
    from sentence_transformers import SentenceTransformer

    ids = [row[0] for row in rows]
    texts = [row[1] for row in rows]
    model = encoder or SentenceTransformer(embedding_model, device=embedding_device)

    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), embedding_batch_size):
        stop = min(start + embedding_batch_size, len(texts))
        encoded = model.encode(
            texts[start:stop],
            batch_size=min(embedding_batch_size, stop - start),
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        chunks.append(np.asarray(encoded).astype(np.float32))
        pause_between_batches(thermal_pause_seconds)

    embeddings = np.vstack(chunks)
    dim = embeddings.shape[1] if embeddings.size else embedding_dimension

    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=len(embeddings), ef_construction=200, M=16)
    index.add_items(embeddings, np.arange(len(ids)))

    # Persist the large, independently readable matrix before asking the native
    # index to serialize.  A failed native write therefore still leaves only
    # staging bytes; the caller can discard them without touching the selected
    # generation.
    np.savez(str(embeddings_path), ids=np.array(ids, dtype=object), vectors=embeddings)
    index.save_index(str(index_path))
    return len(ids), int(dim)


def build_embedding_generation(
    *,
    rows: Sequence[tuple[object, str]],
    index_dir: Path,
    embedding_model: str,
    embedding_device: str,
    embedding_dimension: int = 1024,
    embedding_batch_size: int = 32,
    thermal_pause_seconds: float = 0.0,
    encoder: object | None = None,
    basis_kind: str = "embedding",
    projection_rule_version: str = "policyos.embedding_projection.v1",
    legacy_embeddings_path: Path | None = None,
    legacy_index_path: Path | None = None,
) -> tuple[int, int]:
    """Build, validate, and atomically select one immutable embedding generation.

    The selector is the only authoritative pointer after this function returns.
    Existing flat files are copied only as a compatibility projection and are
    never used when a selector is present.  A failed build cleans up only its
    own staging directory, leaving the previous selector and generation intact.
    ``encoder`` lets a caller reuse the exact loaded model whose asset identity
    it recorded while deciding whether an existing generation can be reused.
    """
    normalized_rows = _normalize_rows(rows)
    encoder_identity: GenerationIdentity | None = None
    if normalized_rows:
        if encoder is None:
            from sentence_transformers import SentenceTransformer

            encoder = SentenceTransformer(embedding_model, device=embedding_device)
        encoder_identity = derive_encoder_identity(encoder)

    def _stage(staging: Path) -> tuple[int, int]:
        if normalized_rows:
            return build_embedding_index(
                rows=normalized_rows,
                embeddings_path=staging / "embeddings.npz",
                index_path=staging / "index.hnsw",
                embedding_model=embedding_model,
                embedding_device=embedding_device,
                embedding_dimension=embedding_dimension,
                embedding_batch_size=embedding_batch_size,
                thermal_pause_seconds=thermal_pause_seconds,
                encoder=encoder,
            )
        dimension = int(embedding_dimension)
        np.savez(
            str(staging / "embeddings.npz"),
            ids=np.array([], dtype=object),
            vectors=np.empty((0, dimension), dtype=np.float32),
        )
        return 0, dimension

    return _publish_embedding_generation(
        normalized_rows=normalized_rows,
        index_dir=index_dir,
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        basis_kind=basis_kind,
        projection_rule_version=projection_rule_version,
        encoder_identity=encoder_identity,
        legacy_embeddings_path=legacy_embeddings_path,
        legacy_index_path=legacy_index_path,
        stage_builder=_stage,
    )


def _build_embedding_generation_from_vectors(
    *,
    rows: Sequence[tuple[object, str]],
    vectors: np.ndarray,
    index_dir: Path,
    embedding_model: str,
    embedding_device: str,
    embedding_dimension: int,
    basis_kind: str,
    projection_rule_version: str,
    encoder_identity: GenerationIdentity,
    legacy_embeddings_path: Path | None = None,
    legacy_index_path: Path | None = None,
) -> tuple[int, int]:
    """Publish a complete generation from validated, precomputed vectors.

    This internal seam exists for domain builders that can prove record-level
    reuse before publication.  The public publisher remains the sole owner of
    staging, inventory, basis, selector, and compatibility-file publication.
    """
    normalized_rows = _normalize_rows(rows)
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("precomputed embedding vectors must be two-dimensional")
    if matrix.shape != (len(normalized_rows), int(embedding_dimension)):
        raise ValueError("precomputed embedding vectors do not match rows or dimension")
    if not np.isfinite(matrix).all():
        raise ValueError("precomputed embedding vectors must be finite")

    def _stage(staging: Path) -> tuple[int, int]:
        if not normalized_rows:
            np.savez(
                str(staging / "embeddings.npz"),
                ids=np.array([], dtype=object),
                vectors=matrix,
            )
            return 0, int(embedding_dimension)

        import hnswlib

        index = hnswlib.Index(space="cosine", dim=int(embedding_dimension))
        index.init_index(max_elements=len(normalized_rows), ef_construction=200, M=16)
        index.add_items(matrix, np.arange(len(normalized_rows)))
        np.savez(
            str(staging / "embeddings.npz"),
            ids=np.array([identifier for identifier, _ in normalized_rows], dtype=object),
            vectors=matrix,
        )
        index.save_index(str(staging / "index.hnsw"))
        return len(normalized_rows), int(embedding_dimension)

    return _publish_embedding_generation(
        normalized_rows=normalized_rows,
        index_dir=index_dir,
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        basis_kind=basis_kind,
        projection_rule_version=projection_rule_version,
        encoder_identity=encoder_identity,
        legacy_embeddings_path=legacy_embeddings_path,
        legacy_index_path=legacy_index_path,
        stage_builder=_stage,
    )


def _publish_embedding_generation(
    *,
    normalized_rows: list[tuple[str, str]],
    index_dir: Path,
    embedding_model: str,
    embedding_device: str,
    basis_kind: str,
    projection_rule_version: str,
    encoder_identity: GenerationIdentity | None,
    legacy_embeddings_path: Path | None,
    legacy_index_path: Path | None,
    stage_builder: Callable[[Path], tuple[int, int]],
) -> tuple[int, int]:
    """Run the shared EMB-02 staged publication for one complete membership."""
    index_dir.mkdir(parents=True, exist_ok=True)
    generation_root = index_dir / GENERATION_ROOT_DIRNAME
    generation_root.mkdir(parents=True, exist_ok=True)
    generation_id = uuid.uuid4().hex
    staging: Path | None = Path(tempfile.mkdtemp(prefix=f".{generation_id}-", dir=generation_root))
    final_dir = generation_root / generation_id
    try:
        if staging is None:
            raise RuntimeError("embedding generation staging was committed too early")
        count, dimension = stage_builder(staging)
        actual_ids, actual_dimension = _read_embedding_matrix(
            staging / "embeddings.npz", require_sorted=True
        )
        if actual_ids != tuple(identifier for identifier, _ in normalized_rows):
            raise ValueError("embedding matrix IDs differ from canonical input order")
        if len(actual_ids) != count or actual_dimension != int(dimension):
            raise ValueError("embedding matrix shape differs from the build result")

        status: Literal["complete", "empty_generation"] = (
            "complete" if count else "empty_generation"
        )
        generator_rule_version = _generator_rule_version(
            projection_rule_version=projection_rule_version,
            embedding_model=embedding_model,
            embedding_device=embedding_device,
            embedding_dimension=actual_dimension,
            encoder_identity=encoder_identity,
        )
        if normalized_rows:
            if encoder_identity is None:
                raise ValueError("non-empty embedding generation requires encoder identity")
            basis = build_generation_basis(
                basis_kind=basis_kind,
                generator_rule_version=generator_rule_version,
                members=[
                    (identifier, text.encode("utf-8")) for identifier, text in normalized_rows
                ],
            ).to_dict()
        else:
            basis = _empty_generation_basis(
                basis_kind=basis_kind,
                generator_rule_version=generator_rule_version,
            )

        atomic_write_json(staging / "ids.json", list(actual_ids))
        atomic_write_json(staging / "basis.json", basis)
        files = {
            "embeddings": _file_record(staging / "embeddings.npz"),
            "ids": _file_record(staging / "ids.json"),
            "basis": _file_record(staging / "basis.json"),
        }
        if status == "complete":
            files["index"] = _file_record(staging / "index.hnsw")
        inventory: dict[str, object] = {
            "schema_version": GENERATION_INVENTORY_SCHEMA_VERSION,
            "generation_id": generation_id,
            "status": status,
            "embedding_model": embedding_model,
            "embedding_device": embedding_device,
            "embedding_dimension": actual_dimension,
            "count": count,
            "ids": list(actual_ids),
            "basis": basis,
            "files": files,
        }
        atomic_write_json(staging / "inventory.json", inventory)
        _validate_generation_directory(
            generation_dir=staging,
            inventory=inventory,
            expected_generation_id=generation_id,
        )

        atomic_commit_path(staging, final_dir)
        staging = None
        inventory_path = final_dir / "inventory.json"
        selector = {
            "schema_version": GENERATION_SELECTOR_SCHEMA_VERSION,
            "generation_id": generation_id,
            "status": status,
            "inventory": f"{GENERATION_ROOT_DIRNAME}/{generation_id}/inventory.json",
            "inventory_sha256": sha256_file(inventory_path),
        }

        atomic_write_json(index_dir / GENERATION_SELECTOR_FILENAME, selector)
        # The selector commits the immutable generation. Compatibility aliases
        # are projections only and may fail independently after readers have a
        # complete authoritative generation to resolve.
        if status == "complete":
            if legacy_embeddings_path is not None:
                _atomic_copy_file(final_dir / "embeddings.npz", legacy_embeddings_path)
            if legacy_index_path is not None:
                _atomic_copy_file(final_dir / "index.hnsw", legacy_index_path)
        return count, actual_dimension
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)


def resolve_embedding_generation(
    index_dir: Path,
    *,
    legacy_embeddings_path: Path | None = None,
    legacy_index_path: Path | None = None,
) -> EmbeddingGenerationRef | None:
    """Resolve a selected generation or, only without a selector, legacy files.

    A present but malformed selector fails closed.  It must never silently fall
    back to a stale flat pair, because that would make a failed/empty generation
    appear current to readers and publishers.
    """
    index_dir = Path(index_dir)
    selector_path = index_dir / GENERATION_SELECTOR_FILENAME
    if selector_path.exists():
        try:
            selector = _read_json_object(selector_path)
            return _resolve_selected_generation(index_dir, selector_path, selector)
        except (
            OSError,
            TypeError,
            ValueError,
            KeyError,
            AttributeError,
            IndexError,
            json.JSONDecodeError,
        ):
            return None

    if legacy_embeddings_path is None or legacy_index_path is None:
        return None
    if not legacy_embeddings_path.is_file() or not legacy_index_path.is_file():
        return None
    try:
        ids, dimension = _read_embedding_matrix(legacy_embeddings_path)
        if not _legacy_index_matches_matrix(
            embeddings_path=legacy_embeddings_path,
            index_path=legacy_index_path,
            ids=ids,
            dimension=dimension,
        ):
            return None
    except (
        ImportError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ):
        return None
    return EmbeddingGenerationRef(
        generation_id="legacy-flat",
        status="legacy",
        root_dir=index_dir,
        embeddings_path=legacy_embeddings_path,
        index_path=legacy_index_path,
        ids_path=None,
        basis_path=None,
        inventory_path=None,
        selector_path=None,
        ids=ids,
        dimension=dimension,
        inventory={},
        selected=False,
    )


def embedding_generation_manifest(
    index_dir: Path,
    *,
    legacy_embeddings_path: Path | None = None,
    legacy_index_path: Path | None = None,
) -> tuple[dict[str, object], tuple[Path, ...]] | None:
    """Return publish metadata and authoritative files for one index directory."""
    selector_path = Path(index_dir) / GENERATION_SELECTOR_FILENAME
    selected = selector_path.exists()
    reference = resolve_embedding_generation(
        Path(index_dir),
        legacy_embeddings_path=legacy_embeddings_path,
        legacy_index_path=legacy_index_path,
    )
    if selected and reference is None:
        raise ValueError("embedding generation selector is invalid or incomplete")
    if reference is None:
        return None

    if reference.selected:
        if reference.inventory_path is None:
            raise ValueError("selected embedding generation has no inventory")
        files_value = reference.inventory.get("files")
        files = cast("Mapping[str, object]", files_value)
        artifact_paths = [selector_path, reference.inventory_path]
        for raw_spec in files.values():
            spec = cast("Mapping[str, object]", raw_spec)
            artifact_paths.append(reference.root_dir / str(spec["path"]))
    else:
        artifact_paths = [
            path
            for path in (legacy_embeddings_path, legacy_index_path)
            if path is not None and path.exists()
        ]

    basis = reference.inventory.get("basis")
    basis_digest = basis.get("basis_digest") if isinstance(basis, dict) else ""
    metadata = {
        "generation_id": reference.generation_id,
        "status": reference.status,
        "selector": str(reference.selector_path) if reference.selector_path else "",
        "inventory": str(reference.inventory_path) if reference.inventory_path else "",
        "basis_digest": str(basis_digest or ""),
        "count": len(reference.ids),
        "embedding_dimension": reference.dimension,
        "embedding_model": str(reference.inventory.get("embedding_model") or ""),
    }
    return metadata, tuple(dict.fromkeys(artifact_paths))


def _normalize_rows(rows: Sequence[tuple[object, str]]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for identifier, text in rows:
        normalized_id = str(identifier)
        if not normalized_id:
            raise ValueError("embedding identifiers must be non-empty")
        if normalized_id in seen:
            raise ValueError(f"embedding identifiers must be unique: {normalized_id}")
        seen.add(normalized_id)
        normalized.append((normalized_id, str(text)))
    return sorted(normalized, key=lambda row: row[0])


def _generator_rule_version(
    *,
    projection_rule_version: str,
    embedding_model: str,
    embedding_device: str,
    embedding_dimension: int,
    encoder_identity: GenerationIdentity | None = None,
) -> str:
    encoder_content = (
        encoder_identity.content_identity if encoder_identity is not None else "unbound"
    )
    return (
        f"{projection_rule_version}|model={embedding_model}|device={embedding_device}"
        f"|dimension={embedding_dimension}|encoder={encoder_content}"
    )


def derive_encoder_identity(encoder: object) -> GenerationIdentity:
    """Fingerprint loaded encoder weights, tokenizer assets, and architecture.

    Model names are labels and can resolve to changed assets. The identity
    therefore includes the live state dictionary and tokenizer vocabulary/config
    that produced the vectors. Unsupported encoder objects fail closed.
    """
    state_dict_method = getattr(encoder, "state_dict", None)
    if not callable(state_dict_method):
        raise ValueError("encoder does not expose a state dictionary")
    state_dict = state_dict_method()
    if not isinstance(state_dict, Mapping) or not state_dict:
        raise ValueError("encoder state dictionary is empty or malformed")

    digest = hashlib.sha256()
    for name in sorted(str(key) for key in state_dict):
        value = state_dict[name]
        raw, dtype, shape = _tensor_bytes(value)
        _hash_frame(digest, name.encode("utf-8"))
        _hash_frame(digest, dtype.encode("utf-8"))
        _hash_frame(digest, _canonical_json(list(shape)))
        _hash_frame(digest, raw)

    modules_method = getattr(encoder, "modules", None)
    modules = list(modules_method()) if callable(modules_method) else [encoder]
    module_config: list[dict[str, object]] = []
    tokenizers: list[tuple[str, object]] = []
    for module_index, module in enumerate(modules):
        module_config.append(
            {
                "class": f"{type(module).__module__}.{type(module).__qualname__}",
                "config": _module_config(module),
            }
        )
        tokenizer = getattr(module, "tokenizer", None)
        if tokenizer is not None:
            tokenizers.append((str(module_index), tokenizer))
    direct_tokenizer = getattr(encoder, "tokenizer", None)
    if direct_tokenizer is not None and all(
        direct_tokenizer is not existing for _index, existing in tokenizers
    ):
        tokenizers.append(("direct", direct_tokenizer))
    if not tokenizers:
        raise ValueError("encoder does not expose its tokenizer assets")

    tokenizer_material: list[dict[str, object]] = []
    for name, tokenizer in tokenizers:
        vocab_method = getattr(tokenizer, "get_vocab", None)
        vocabulary = vocab_method() if callable(vocab_method) else None
        if not isinstance(vocabulary, Mapping) or not vocabulary:
            raise ValueError("encoder tokenizer vocabulary is unavailable")
        backend = getattr(tokenizer, "backend_tokenizer", None)
        backend_json = backend.to_str() if callable(getattr(backend, "to_str", None)) else None
        sentencepiece = getattr(tokenizer, "sp_model", None)
        sentencepiece_bytes = None
        if callable(getattr(sentencepiece, "serialized_model_proto", None)):
            sentencepiece_bytes = sentencepiece.serialized_model_proto().hex()
        tokenizer_material.append(
            {
                "name": name,
                "class": f"{type(tokenizer).__module__}.{type(tokenizer).__qualname__}",
                "vocabulary": sorted(
                    (str(token), int(index)) for token, index in vocabulary.items()
                ),
                "special_tokens": _jsonable(getattr(tokenizer, "special_tokens_map", {})),
                "settings": _tokenizer_settings(tokenizer),
                "added_vocabulary": _jsonable(
                    getattr(tokenizer, "get_added_vocab", lambda: {})()
                ),
                "backend": backend_json,
                "sentencepiece": sentencepiece_bytes,
            }
        )
    _hash_frame(digest, _canonical_json(module_config))
    _hash_frame(digest, _canonical_json(tokenizer_material))
    return GenerationIdentity(content_identity=f"sha256:{digest.hexdigest()}")


def _tensor_bytes(value: object) -> tuple[bytes, str, tuple[int, ...]]:
    detach = getattr(value, "detach", None)
    if callable(detach):
        tensor = detach().cpu().contiguous()
        dtype = str(getattr(tensor, "dtype", ""))
        shape_value = getattr(tensor, "shape", ())
        shape = tuple(int(item) for item in shape_value)
        view = getattr(tensor, "view", None)
        if callable(view):
            with suppress(ImportError, TypeError, RuntimeError):
                tensor = view(__import__("torch").uint8)
        numpy_value = tensor.numpy()
    else:
        numpy_value = np.asarray(value)
        dtype = str(numpy_value.dtype)
        shape = tuple(int(item) for item in numpy_value.shape)
    if not hasattr(numpy_value, "tobytes"):
        raise ValueError("encoder state dictionary contains an unsupported tensor")
    return numpy_value.tobytes(order="C"), dtype, shape


def _module_config(module: object) -> object:
    module_config_method = getattr(module, "get_config_dict", None)
    if callable(module_config_method):
        config_value = module_config_method()
    else:
        config = getattr(module, "config", None)
        to_dict = getattr(config, "to_dict", None)
        config_value = to_dict() if callable(to_dict) else config
    projection_fields = (
        "pooling_mode_cls_token",
        "pooling_mode_mean_tokens",
        "pooling_mode_max_tokens",
        "pooling_mode_mean_sqrt_len_tokens",
        "pooling_mode_weightedmean_tokens",
        "pooling_mode_lasttoken",
        "max_seq_length",
        "do_lower_case",
        "normalize_embeddings",
    )
    return {
        "config": _jsonable(config_value) if config_value is not None else {},
        "projection": {
            name: _jsonable(getattr(module, name))
            for name in projection_fields
            if hasattr(module, name)
        },
    }


def _tokenizer_settings(tokenizer: object) -> dict[str, object]:
    """Capture tokenizer behavior settings without binding cache locations."""
    settings: dict[str, object] = {}
    for name in (
        "model_max_length",
        "padding_side",
        "truncation_side",
        "clean_up_tokenization_spaces",
        "model_input_names",
        "do_lower_case",
        "add_prefix_space",
        "strip_accents",
        "tokenize_chinese_chars",
    ):
        if hasattr(tokenizer, name):
            settings[name] = _jsonable(getattr(tokenizer, name))
    init_kwargs = getattr(tokenizer, "init_kwargs", None)
    if isinstance(init_kwargs, Mapping):
        settings["init_kwargs"] = {
            str(key): _jsonable(value)
            for key, value in init_kwargs.items()
            if not str(key).endswith(("_file", "_path"))
            and str(key) not in {"name_or_path", "_name_or_path"}
        }
    return settings


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, set):
        return sorted((_jsonable(item) for item in value), key=repr)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        return _jsonable(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(getattr(value, "content", None), str):
        return {
            "content": value.content,
            "lstrip": bool(getattr(value, "lstrip", False)),
            "rstrip": bool(getattr(value, "rstrip", False)),
            "normalized": bool(getattr(value, "normalized", False)),
            "special": bool(getattr(value, "special", False)),
        }
    raise ValueError(f"encoder configuration contains unsupported value: {type(value)!r}")


def _hash_frame(digest: hashlib._Hash, raw: bytes) -> None:
    digest.update(len(raw).to_bytes(8, "big"))
    digest.update(raw)


def _legacy_index_matches_matrix(
    *,
    embeddings_path: Path,
    index_path: Path,
    ids: tuple[str, ...],
    dimension: int,
) -> bool:
    """Prove a selector-less legacy HNSW index matches its flat matrix."""
    return _hnsw_file_matches_matrix(
        embeddings_path=embeddings_path,
        index_path=index_path,
        ids=ids,
        dimension=dimension,
    )


def _hnsw_file_matches_matrix(
    *,
    embeddings_path: Path,
    index_path: Path,
    ids: tuple[str, ...],
    dimension: int,
) -> bool:
    """Load a native index and compare its labels and vectors to the matrix."""
    import hnswlib

    with np.load(str(embeddings_path), allow_pickle=True) as payload:
        vectors = np.asarray(payload["vectors"], dtype=np.float32)
    if not index_path.is_file() or vectors.shape != (len(ids), dimension) or not len(ids):
        return False
    index = hnswlib.Index(space="cosine", dim=dimension)
    index.load_index(str(index_path), max_elements=len(ids))
    return hnsw_index_matches_vectors(index, vectors)


def hnsw_index_matches_vectors(index: object, vectors: np.ndarray) -> bool:
    """Check that HNSW labels and stored vectors bind to the supplied matrix."""
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or not matrix.shape[0] or not np.isfinite(matrix).all():
        return False
    try:
        if int(index.get_current_count()) != matrix.shape[0]:
            return False
        labels = tuple(int(value) for value in index.get_ids_list())
        if set(labels) != set(range(matrix.shape[0])):
            return False
        stored = np.asarray(index.get_items(np.arange(matrix.shape[0])), dtype=np.float32)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False
    return stored.shape == matrix.shape and bool(
        np.allclose(stored, matrix, rtol=0.0, atol=1e-6)
    )


def generation_basis_matches_members(
    reference: EmbeddingGenerationRef,
    *,
    basis_kind: str,
    members: Sequence[tuple[str, bytes]],
) -> bool:
    """Reconcile a selected generation basis against current consumer inputs."""
    if not reference.selected or reference.status != "complete":
        return False
    raw_basis = reference.inventory.get("basis")
    if not isinstance(raw_basis, Mapping):
        return False
    generator_rule_version = raw_basis.get("generator_rule_version")
    if not isinstance(generator_rule_version, str) or not generator_rule_version:
        return False
    try:
        current = build_generation_basis(
            basis_kind=basis_kind,
            generator_rule_version=generator_rule_version,
            members=members,
        )
    except (TypeError, ValueError):
        return False
    return current.to_dict() == dict(raw_basis)


def _empty_generation_basis(*, basis_kind: str, generator_rule_version: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": GENERATION_BASIS_SCHEMA_VERSION,
        "basis_kind": basis_kind,
        "generator_rule_version": generator_rule_version,
        "members": [],
    }
    return {**payload, "basis_digest": f"sha256:{sha256_bytes(_canonical_json(payload))}"}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _file_record(path: Path) -> dict[str, object]:
    return {
        "path": path.name,
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def _read_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return {str(key): item for key, item in value.items()}


def _read_embedding_matrix(
    path: Path, *, require_sorted: bool = False
) -> tuple[tuple[str, ...], int]:
    with np.load(str(path), allow_pickle=True) as payload:
        if "ids" not in payload or "vectors" not in payload:
            raise ValueError("embedding matrix is missing ids or vectors")
        raw_ids = payload["ids"].tolist()
        ids = tuple(str(identifier) for identifier in raw_ids)
        vectors = np.asarray(payload["vectors"])
    if vectors.ndim != 2:
        raise ValueError("embedding vectors must be two-dimensional")
    if vectors.shape[0] != len(ids):
        raise ValueError("embedding vector rows do not match IDs")
    if vectors.shape[1] < 1:
        raise ValueError("embedding dimension must be positive")
    if len(ids) != len(set(ids)):
        raise ValueError("embedding IDs must be unique")
    if require_sorted and ids != tuple(sorted(ids)):
        raise ValueError("embedding IDs must be sorted")
    return ids, int(vectors.shape[1])


def _resolve_selected_generation(
    index_dir: Path,
    selector_path: Path,
    selector: Mapping[str, object],
) -> EmbeddingGenerationRef:
    if selector.get("schema_version") != GENERATION_SELECTOR_SCHEMA_VERSION:
        raise ValueError("unsupported embedding selector schema")
    generation_id = selector.get("generation_id")
    status = selector.get("status")
    inventory_raw = selector.get("inventory")
    inventory_sha256 = selector.get("inventory_sha256")
    if (
        not isinstance(generation_id, str)
        or _GENERATION_ID_PATTERN.fullmatch(generation_id) is None
        or status not in {"complete", "empty_generation"}
        or not isinstance(inventory_raw, str)
        or Path(inventory_raw).is_absolute()
        or not isinstance(inventory_sha256, str)
    ):
        raise ValueError("embedding selector fields are invalid")
    inventory_path = _safe_child(index_dir, inventory_raw)
    if not inventory_path.is_file() or sha256_file(inventory_path) != inventory_sha256:
        raise ValueError("embedding inventory is missing or does not match selector")
    inventory = _read_json_object(inventory_path)
    return _build_selected_reference(
        selector_path=selector_path,
        inventory_path=inventory_path,
        inventory=inventory,
        generation_id=generation_id,
        status=cast("Literal['complete', 'empty_generation']", status),
    )


def _build_selected_reference(
    *,
    selector_path: Path,
    inventory_path: Path,
    inventory: Mapping[str, object],
    generation_id: str,
    status: Literal["complete", "empty_generation"],
    allow_staging: bool = False,
) -> EmbeddingGenerationRef:
    if inventory.get("schema_version") != GENERATION_INVENTORY_SCHEMA_VERSION:
        raise ValueError("unsupported embedding inventory schema")
    if inventory.get("generation_id") != generation_id or inventory.get("status") != status:
        raise ValueError("embedding inventory does not match selector")
    generation_dir = inventory_path.parent
    if generation_dir.name != generation_id and not (
        allow_staging and generation_dir.name.startswith(f".{generation_id}-")
    ):
        raise ValueError("embedding inventory is outside its generation directory")
    try:
        raw_ids = inventory["ids"]
        raw_files = inventory["files"]
        raw_basis = inventory["basis"]
        if (
            not isinstance(raw_ids, list)
            or not isinstance(raw_files, Mapping)
            or not isinstance(raw_basis, Mapping)
        ):
            raise ValueError("embedding inventory collections are invalid")
        ids = tuple(str(identifier) for identifier in raw_ids)
        dimension = int(inventory["embedding_dimension"])
        count = int(inventory["count"])
        files = raw_files
        basis = raw_basis
    except (KeyError, TypeError, ValueError):
        raise ValueError("embedding inventory fields are invalid") from None
    if dimension < 1 or count != len(ids) or ids != tuple(sorted(ids)):
        raise ValueError("embedding inventory IDs or dimension are invalid")
    expected_files = {"embeddings", "ids", "basis"}
    if status == "complete":
        expected_files.add("index")
        if count == 0:
            raise ValueError("complete embedding generation cannot be empty")
    elif count != 0 or "index" in files:
        raise ValueError("empty embedding generation must not publish an index")
    if set(files) != expected_files:
        raise ValueError("embedding inventory file set is incomplete")

    paths: dict[str, Path] = {}
    for name, raw_spec in files.items():
        if not isinstance(raw_spec, Mapping):
            raise ValueError("embedding inventory file descriptor is invalid")
        spec = cast("Mapping[str, object]", raw_spec)
        raw_path = spec.get("path")
        expected_hash = spec.get("sha256")
        expected_size = spec.get("size")
        if (
            not isinstance(raw_path, str)
            or Path(raw_path).is_absolute()
            or not isinstance(expected_hash, str)
            or not isinstance(expected_size, int)
        ):
            raise ValueError("embedding inventory file descriptor is invalid")
        path = _safe_child(generation_dir, raw_path)
        if (
            not path.is_file()
            or path.stat().st_size != expected_size
            or sha256_file(path) != expected_hash
        ):
            raise ValueError(f"embedding generation member is missing or corrupt: {name}")
        paths[name] = path

    matrix_ids, matrix_dimension = _read_embedding_matrix(paths["embeddings"], require_sorted=True)
    if matrix_ids != ids or matrix_dimension != dimension:
        raise ValueError("embedding matrix is not bound to inventory IDs/dimension")
    persisted_ids = json.loads(paths["ids"].read_text(encoding="utf-8"))
    if persisted_ids != list(ids):
        raise ValueError("embedding IDs sidecar is not bound to the matrix")
    persisted_basis = _read_json_object(paths["basis"])
    if dict(persisted_basis) != dict(basis):
        raise ValueError("embedding basis sidecar is not bound to inventory")
    _validate_basis(persisted_basis, ids)
    if status == "complete" and not _hnsw_file_matches_matrix(
        embeddings_path=paths["embeddings"],
        index_path=paths["index"],
        ids=ids,
        dimension=dimension,
    ):
        raise ValueError("HNSW index vectors do not match the matrix")
    return EmbeddingGenerationRef(
        generation_id=generation_id,
        status=status,
        root_dir=generation_dir,
        embeddings_path=paths["embeddings"],
        index_path=paths.get("index"),
        ids_path=paths["ids"],
        basis_path=paths["basis"],
        inventory_path=inventory_path,
        selector_path=selector_path,
        ids=ids,
        dimension=dimension,
        inventory=dict(inventory),
        selected=True,
    )


def _validate_generation_directory(
    *, generation_dir: Path, inventory: Mapping[str, object], expected_generation_id: str
) -> None:
    _build_selected_reference(
        selector_path=generation_dir.parent.parent / GENERATION_SELECTOR_FILENAME,
        inventory_path=generation_dir / "inventory.json",
        inventory=inventory,
        generation_id=expected_generation_id,
        status=cast("Literal['complete', 'empty_generation']", inventory["status"]),
        allow_staging=True,
    )


def _validate_basis(basis: Mapping[str, object], ids: tuple[str, ...]) -> None:
    if basis.get("schema_version") != GENERATION_BASIS_SCHEMA_VERSION:
        raise ValueError("embedding basis schema is unsupported")
    members = basis.get("members")
    if not isinstance(members, list):
        raise ValueError("embedding basis members are invalid")
    member_ids: list[str] = []
    for member in members:
        if not isinstance(member, Mapping) or set(member) != {"identifier", "content_identity"}:
            raise ValueError("embedding basis member is invalid")
        identifier = member.get("identifier")
        content_identity = member.get("content_identity")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("embedding basis identifier is invalid")
        if not isinstance(content_identity, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", content_identity
        ):
            raise ValueError("embedding basis content identity is invalid")
        member_ids.append(identifier)
    if tuple(member_ids) != ids:
        raise ValueError("embedding basis identifiers are not bound to embedding IDs")
    basis_digest = basis.get("basis_digest")
    payload = {key: value for key, value in basis.items() if key != "basis_digest"}
    expected_digest = f"sha256:{sha256_bytes(_canonical_json(payload))}"
    if not isinstance(basis_digest, str) or basis_digest != expected_digest:
        raise ValueError("embedding basis digest is invalid")


def _safe_child(root: Path, raw_path: str) -> Path:
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise ValueError("embedding generation path escapes its root") from None
    return candidate


def _atomic_copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        shutil.copyfile(source, tmp_path)
        atomic_commit_path(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


__all__ = [
    "GENERATION_INVENTORY_SCHEMA_VERSION",
    "GENERATION_ROOT_DIRNAME",
    "GENERATION_SELECTOR_FILENAME",
    "GENERATION_SELECTOR_SCHEMA_VERSION",
    "EmbeddingGenerationRef",
    "build_embedding_generation",
    "build_embedding_index",
    "embedding_generation_manifest",
    "generation_basis_matches_members",
    "hnsw_index_matches_vectors",
    "resolve_embedding_generation",
]
