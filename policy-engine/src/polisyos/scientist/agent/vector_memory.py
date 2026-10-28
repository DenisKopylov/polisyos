"""HNSW-backed vector memory with same-object and exact-CAS snapshot custody."""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import logging
import math
import struct
import sys
import tempfile
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

try:
    import hnswlib

    _HAS_HNSW = True
except ImportError:
    _HAS_HNSW = False

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore, CoreJSONArtifactBoundedMemberReader

_logger = logging.getLogger(__name__)
_INDEX_ROLE = "vector_memory_index"
_BUNDLE_V2 = "2.0"
_BUNDLE_ROWS = "3.0"
_ROWS_ROLE = "vector_memory_vectors"
_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_JSON_BYTES = 256 * 1024
_MAX_ROWS_BYTES = 5 * 1024 * 1024
_MAX_ROWS_ELEMENTS = 1_000_000
_MAX_ROWS = 25_000
_MAX_DIM = 4096
_MAX_CAPACITY = 100_000
_MAX_M = 64
_MAX_EF = 1000
_MAX_NATIVE_BASE_BYTES = 64 * 1024 * 1024
_MAX_REBUILD_WORK = 16_000_000


class UntrustedNativeVectorBundleError(ValueError):
    """A nonportable or unselected vector bundle cannot enter this consumer."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _require_row_resource_bounds(*, dim: int, capacity: int, count: int, M: int, ef: int) -> None:
    base_bytes = capacity * (2 * M * 4 + 4 + dim * 4 + 8)
    if (
        not 1 <= dim <= _MAX_DIM
        or not 1 <= capacity <= _MAX_CAPACITY
        or not 0 <= count <= min(capacity, _MAX_ROWS)
        or count * dim > _MAX_ROWS_ELEMENTS
        or not 2 <= M <= _MAX_M
        or not M <= ef <= _MAX_EF
        or base_bytes > _MAX_NATIVE_BASE_BYTES
        or count * M * ef > _MAX_REBUILD_WORK
    ):
        raise ValueError("vector_memory_rows_resource_limit")


type IndexBindingStatus = Literal[
    "in_memory",
    "exact_selected",
    "legacy_default_at_read",
    "modified_after_exact",
    "modified_after_legacy",
    "rows_selected",
    "modified_after_rows",
]


def _require_row_metadata_bounds(
    keys: tuple[str, ...], metadata: tuple[dict[str, Any], ...]
) -> None:
    """Reject oversized owned data before serializing the portable bundle."""
    if (
        len(keys) != len(metadata)
        or len(keys) > _MAX_ROWS
        or any(not key or len(key) > 1024 for key in keys)
    ):
        raise ValueError("vector_memory_row_key_limit")
    elements = 0
    characters = 0
    stack: list[tuple[object, int]] = [(value, 0) for value in keys]
    stack.extend((value, 0) for value in metadata)
    while stack:
        value, depth = stack.pop()
        elements += 1
        if elements > 100_000 or depth > 32:
            raise ValueError("vector_memory_rows_json_limit")
        if type(value) is str:
            characters += len(value)
            if characters > _MAX_JSON_BYTES:
                raise ValueError("vector_memory_rows_json_limit")
        elif type(value) is int:
            if value.bit_length() > 4096:
                raise ValueError("vector_memory_rows_json_limit")
        elif type(value) is list:
            if len(value) > 100_000 - elements - len(stack):
                raise ValueError("vector_memory_rows_json_limit")
            stack.extend((item, depth + 1) for item in value)
        elif type(value) is dict:
            if len(value) * 2 > 100_000 - elements - len(stack):
                raise ValueError("vector_memory_rows_json_limit")
            for key, item in value.items():
                stack.append((key, depth + 1))
                stack.append((item, depth + 1))
        elif type(value) is float and not math.isfinite(value):
            raise ValueError("vector_memory_rows_non_finite_metadata")
        elif value is not None and type(value) not in (bool, float):
            raise TypeError("vector_memory_rows_metadata_type_invalid")


def _bounded_reader(store: ArtifactStore) -> CoreJSONArtifactBoundedMemberReader:
    """Require the Core owner seam that enforces selected bounded reads."""
    from polisyos.core.artifacts import CoreJSONArtifactBoundedMemberReader
    from polisyos.core.artifacts.protocol import matches_runtime_protocol

    if not matches_runtime_protocol(store, CoreJSONArtifactBoundedMemberReader):
        raise ValueError("vector_memory_bounded_store_required")
    return store


def _owned_json(value: object, active: set[int] | None = None) -> Any:
    """Copy exact built-in JSON values without calling user-defined copy hooks."""
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Vector memory JSON metadata requires finite numbers")
        return value
    if type(value) not in (dict, list):
        raise TypeError("Vector memory metadata must contain only built-in JSON values")
    if active is None:
        active = set()
    identity = id(value)
    if identity in active:
        raise ValueError("Vector memory JSON metadata cannot contain cycles")
    active.add(identity)
    try:
        if type(value) is list:
            return [_owned_json(item, active) for item in value]
        if any(type(key) is not str for key in value):
            raise TypeError("Vector memory JSON metadata keys must be built-in strings")
        if "_type" in value:
            raise ValueError("Vector memory JSON metadata contains reserved key _type")
        return {key: _owned_json(item, active) for key, item in value.items()}
    finally:
        active.remove(identity)


def _owned_metadata(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("Vector memory metadata must be a built-in JSON object")
    return _owned_json(value)


def _owned_vector(embedding: Any) -> list[float]:
    """Convert vector inputs before acquiring the generation lock."""
    result = [float(value) for value in embedding]
    if any(not math.isfinite(value) for value in result):
        raise ValueError("Vector memory embeddings must contain finite numbers")
    scale = max((abs(value) for value in result), default=0.0)
    if not scale:
        return result
    scaled = [value / scale for value in result]
    norm = math.sqrt(sum(value * value for value in scaled))
    return [value / norm for value in scaled]


def _require_supported_hnsw_abi() -> None:
    """Allow the native header parser only for the pinned, measured ABI."""
    try:
        version = importlib.metadata.version("hnswlib")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("Vector memory native hnswlib version unavailable") from exc
    if (
        version != "0.8.0"
        or sys.byteorder != "little"
        or struct.calcsize("@N") != 8
        or struct.calcsize("@I") != 4
        or struct.calcsize("@f") != 4
    ):
        raise ValueError("Vector memory native ABI is unsupported")


def _validate_native_index_bytes(
    raw: bytes, *, dim: int, max_elements: int, ef_construction: int, M: int, count: int
) -> None:
    """Check bounded native record shape before handing bytes to hnswlib.

    This is not a validator for adversarial native graph topology or producer origin.
    """
    _require_supported_hnsw_abi()
    header = struct.Struct("<6QiI3QdQ")
    if len(raw) < header.size:
        raise ValueError("Vector memory native header is truncated")
    (
        offset0,
        capacity,
        native_count,
        row_size,
        label_offset,
        data_offset,
        _max_level,
        _entry,
        max_m,
        max_m0,
        native_m,
        mult,
        native_ef,
    ) = header.unpack_from(raw)
    if (
        count > max_elements
        or capacity != max_elements
        or native_count != count
        or native_m != M
        or max_m != M
        or max_m0 != 2 * M
        or not 2 <= M <= 10000
        or native_ef != ef_construction
        or ef_construction < M
        or not math.isfinite(mult)
        or mult <= 0
        or offset0 != 0
        or data_offset != max_m0 * 4 + 4
        or label_offset != data_offset + dim * 4
        or row_size != label_offset + 8
    ):
        raise ValueError("Vector memory native header does not match bundle configuration")
    rows_end = header.size + count * row_size
    if rows_end > len(raw):
        raise ValueError("Vector memory native records are truncated")
    labels: set[int] = set()
    for i in range(count):
        row = header.size + i * row_size
        if raw[row + offset0 + 2] & 1:
            raise ValueError("Vector memory native index contains deleted rows")
        label = struct.unpack_from("<Q", raw, row + label_offset)[0]
        labels.add(label)
        if any(
            not math.isfinite(value[0])
            for value in struct.iter_unpack("<f", raw[row + data_offset : row + label_offset])
        ):
            raise ValueError("Vector memory native vector contains non-finite values")
    if labels != set(range(count)):
        raise ValueError("Vector memory native labels do not match the bundle keys")
    cursor = rows_end
    for _ in range(count):
        if cursor + 4 > len(raw):
            raise ValueError("Vector memory native links are truncated")
        size = struct.unpack_from("<I", raw, cursor)[0]
        cursor += 4
        if size % (M * 4 + 4) or size > len(raw) - cursor:
            raise ValueError("Vector memory native links have invalid extent")
        cursor += size
    if cursor != len(raw):
        raise ValueError("Vector memory native index has trailing bytes")


@dataclass(frozen=True, slots=True)
class _Generation:
    dim: int
    max_elements: int
    ef_construction: int
    M: int
    index: Any
    keys: tuple[str, ...]
    metadata: tuple[dict[str, Any], ...]
    key_to_idx: dict[str, int]
    index_binding_status: IndexBindingStatus


class VectorMemoryStore:
    """HNSW-backed nearest-neighbor memory with one same-object generation."""

    def __init__(
        self,
        dim: int = 384,
        max_elements: int = 100_000,
        ef_construction: int = 200,
        M: int = 16,
    ) -> None:
        if not _HAS_HNSW:
            raise ImportError(
                "hnswlib is required for VectorMemoryStore.  Install it with: pip install hnswlib"
            )
        if any(
            type(value) is not int or value <= 0
            for value in (dim, max_elements, ef_construction, M)
        ):
            raise ValueError(
                "Vector memory dimensions, capacity and construction options must be positive integers"
            )
        if M < 2:
            raise ValueError("Vector memory M must be at least two")
        actual_m = min(M, 10000)
        actual_ef = max(ef_construction, actual_m)
        index = hnswlib.Index(space="cosine", dim=dim)
        index.init_index(max_elements=max_elements, ef_construction=actual_ef, M=actual_m)
        index.set_ef(50)
        self._generation_lock = threading.RLock()
        self._generation: _Generation | None = _Generation(
            dim, max_elements, actual_ef, actual_m, index, (), (), {}, "in_memory"
        )

    @classmethod
    def from_portable_artifact(cls, store: ArtifactStore, ref: ArtifactRef) -> VectorMemoryStore:
        """Reopen a bounded row bundle without constructing a native index first."""
        instance = cls.__new__(cls)
        instance._generation_lock = threading.RLock()
        instance._generation = None
        instance.load_from_artifact(store, ref)
        return instance

    def _get_generation(self) -> _Generation:
        generation = self._generation
        if generation is None:
            raise RuntimeError("vector_memory_generation_unavailable_after_failed_rollback")
        return generation

    @property
    def dim(self) -> int:
        """Return the current generation's vector dimension."""
        with self._generation_lock:
            return self._get_generation().dim

    @property
    def index_binding_status(self) -> IndexBindingStatus:
        """Disclose whether the loaded index used an exact or legacy default view."""
        with self._generation_lock:
            return self._get_generation().index_binding_status

    def __len__(self) -> int:
        with self._generation_lock:
            return len(self._get_generation().keys)

    def _save_index_bytes(self) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            self._get_generation().index.save_index(str(index_path))
            return index_path.read_bytes()

    def _restore_index_bytes(self, index_bytes: bytes, generation: _Generation) -> Any:
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            index_path.write_bytes(index_bytes)
            restored = hnswlib.Index(space="cosine", dim=generation.dim)
            restored.load_index(str(index_path), max_elements=generation.max_elements)
            restored.set_ef(50)
        return restored

    def add(self, key: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        """Add or update one vector with an owned built-in JSON metadata object.

        Subclasses, arbitrary objects, cycles, non-string keys, the reserved
        canonical key ``_type`` at any depth and non-finite numbers are refused
        before the generation is touched.
        """
        if type(key) is not str:
            raise TypeError("Vector memory key must be a built-in string")
        vector = _owned_vector(embedding)
        owned_metadata = _owned_metadata(metadata if metadata is not None else {})
        with self._generation_lock:
            generation = self._get_generation()
            if len(vector) != generation.dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {generation.dim}, got {len(vector)}"
                )
            idx = generation.key_to_idx.get(key)
            if idx is None and len(generation.keys) >= generation.max_elements:
                raise RuntimeError(
                    "Vector memory capacity exhausted; resize before adding another element"
                )
            is_new = idx is None
            if idx is None:
                idx = len(generation.keys)
            next_keys = list(generation.keys)
            next_metadata = list(generation.metadata)
            next_key_to_idx = dict(generation.key_to_idx)
            if is_new:
                next_keys.append(key)
                next_metadata.append(owned_metadata)
                next_key_to_idx[key] = idx
            else:
                next_metadata[idx] = owned_metadata
            status = generation.index_binding_status
            if status == "exact_selected":
                status = "modified_after_exact"
            elif status == "legacy_default_at_read":
                status = "modified_after_legacy"
            elif status == "rows_selected":
                status = "modified_after_rows"
            next_generation = replace(
                generation,
                keys=tuple(next_keys),
                metadata=tuple(next_metadata),
                key_to_idx=next_key_to_idx,
                index_binding_status=status,
            )
            snapshot = self._save_index_bytes()
            # Poison before the native mutation; exceptions can never expose a mixed generation.
            self._generation = None
            try:
                generation.index.add_items([vector], [idx])
                self._generation = next_generation
            except BaseException:
                try:
                    restored = self._restore_index_bytes(snapshot, generation)
                    self._generation = replace(generation, index=restored)
                except BaseException as exc:
                    raise RuntimeError(
                        "vector_memory_generation_unavailable_after_failed_rollback"
                    ) from exc
                raise

    def query(
        self,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Read complete key, distance and metadata tuples from one generation."""
        if type(top_k) is not int or top_k < 1:
            raise ValueError("Vector memory top_k must be a positive integer")
        vector = _owned_vector(embedding)
        with self._generation_lock:
            generation = self._get_generation()
            if len(vector) != generation.dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {generation.dim}, got {len(vector)}"
                )
            if not generation.keys:
                return []
            labels, distances = generation.index.knn_query(
                [vector], k=min(top_k, len(generation.keys))
            )
            results: list[tuple[str, float, dict[str, Any]]] = []
            for label, dist in zip(labels[0], distances[0], strict=True):
                idx = int(label)
                if not 0 <= idx < len(generation.keys):
                    raise ValueError("Vector memory native label is outside the generation")
                results.append(
                    (generation.keys[idx], float(dist), _owned_metadata(generation.metadata[idx]))
                )
            return results

    def lookup_metadata(self, key: str) -> dict[str, Any] | None:
        """Return an owned row by its exact key, without a similarity query."""
        if type(key) is not str:
            raise TypeError("Vector memory key must be a built-in string")
        with self._generation_lock:
            generation = self._get_generation()
            idx = generation.key_to_idx.get(key)
            return None if idx is None else _owned_metadata(generation.metadata[idx])

    def save_to_artifact(
        self,
        store: ArtifactStore,
        *,
        emit_v2: bool = False,
        emit_rows: bool = False,
    ) -> ArtifactRef:
        """Write legacy by default, native-v2 or portable row-v3 by explicit opt-in."""
        from polisyos.core.artifacts import (
            artifact_ref_for_manifest,
            artifact_ref_identity_key,
            input_ref_from_artifact_ref,
        )
        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.artifacts.store import PutOptions
        from polisyos.core.canon import CanonSpec

        if type(emit_v2) is not bool or type(emit_rows) is not bool:
            raise TypeError("Vector memory format flags must be booleans")
        if emit_v2 and emit_rows:
            raise ValueError("Vector memory format flags are mutually exclusive")
        with self._generation_lock:
            generation = self._get_generation()
            self._verify_labels(generation.index, len(generation.keys))
            if emit_rows:
                _require_row_metadata_bounds(generation.keys, generation.metadata)
            payload: dict[str, Any] = {
                "dim": generation.dim,
                "max_elements": generation.max_elements,
                "ef_construction": generation.ef_construction,
                "M": generation.M,
                "keys": list(generation.keys),
                "metadata": [_owned_metadata(row) for row in generation.metadata],
            }
            if emit_rows:
                import numpy as np

                from polisyos.foundry.execute import read_numeric_npz_bounded

                _require_row_resource_bounds(
                    dim=generation.dim,
                    capacity=generation.max_elements,
                    count=len(generation.keys),
                    M=generation.M,
                    ef=generation.ef_construction,
                )
                if any(not key or len(key.encode("utf-8")) > 1024 for key in generation.keys):
                    raise ValueError("vector_memory_row_key_limit")
                if generation.keys:
                    vectors = np.asarray(
                        generation.index.get_items(list(range(len(generation.keys)))), dtype="<f4"
                    )
                else:
                    vectors = np.empty((0, generation.dim), dtype="<f4")
                if (
                    vectors.shape != (len(generation.keys), generation.dim)
                    or not np.isfinite(vectors).all()
                ):
                    raise ValueError("vector_memory_rows_invalid")
                stream = io.BytesIO()
                np.savez(stream, vectors=vectors)
                index_bytes = stream.getvalue()
                read_numeric_npz_bounded(
                    index_bytes,
                    names=("vectors",),
                    max_entries=1,
                    max_elements=_MAX_ROWS_ELEMENTS,
                    max_member_bytes=_MAX_ROWS_BYTES,
                    ndim=2,
                    allow_empty=True,
                    exact_dtype="<f4",
                )
            else:
                index_bytes = self._save_index_bytes()

        if emit_rows:
            from polisyos.core.artifacts import CoreJsonReadLimits, read_core_json_artifact_bounded
            from polisyos.core.canon import to_canonical_bytes

            rows_ref = store.put_bytes(
                index_bytes,
                PutOptions(kind="vector_memory.vectors", media_type="application/x-npz"),
                return_selected_profile=True,
            )
            if self._read_rows(store, rows_ref, len(index_bytes)) != index_bytes:
                raise ValueError("vector_memory_rows_written_bytes_mismatch")
            payload["schema_version"] = _BUNDLE_ROWS
            payload["vectors_ref"] = rows_ref.model_dump(mode="json")
            payload["vectors_bytes_len"] = len(index_bytes)
            expected_payload = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
            if len(expected_payload) > _MAX_JSON_BYTES:
                raise ValueError("vector_memory_rows_json_limit")
            bundle_ref = store.put_json(
                payload,
                PutOptions(
                    kind="vector_memory.bundle",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="3.0"),
                    inputs=[input_ref_from_artifact_ref(rows_ref, role=_ROWS_ROLE)],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            written = read_core_json_artifact_bounded(
                _bounded_reader(store),
                bundle_ref,
                limits=CoreJsonReadLimits(
                    max_bytes=_MAX_JSON_BYTES,
                    max_depth=32,
                    max_elements=100_000,
                    max_manifest_bytes=_MAX_MANIFEST_BYTES,
                ),
            )
            if (
                written.raw_payload_bytes != expected_payload
                or written.manifest.kind != "vector_memory.bundle"
                or written.manifest.media_type != "application/json"
                or written.manifest.artifact_schema
                != SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="3.0")
                or [edge for edge in written.manifest.inputs if edge.role == _ROWS_ROLE]
                != [input_ref_from_artifact_ref(rows_ref, role=_ROWS_ROLE)]
            ):
                raise ValueError("vector_memory_rows_written_bundle_mismatch")
            return bundle_ref

        payload["index_bytes_len"] = len(index_bytes)
        store.put_json(
            payload,
            PutOptions(kind="vector_memory.meta", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        index_ref = store.put_bytes(
            index_bytes,
            PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        self._read_index(store, index_ref, len(index_bytes), expected_bytes=index_bytes)
        if emit_v2:
            payload["schema_version"] = _BUNDLE_V2
            payload["index_ref"] = index_ref.model_dump(mode="json")
            schema = SchemaInfo(name="polisyos.scientist.VectorMemoryBundle", version="2.0")
            inputs = [input_ref_from_artifact_ref(index_ref, role=_INDEX_ROLE)]
        else:
            default_ref = artifact_ref_for_manifest(store.get_manifest(index_ref.artifact_id))
            if artifact_ref_identity_key(default_ref) != artifact_ref_identity_key(index_ref):
                raise ValueError(
                    "Vector memory legacy bundle cannot bind non-default index profile"
                )
            payload["index_artifact_id"] = str(index_ref.artifact_id)
            schema = None
            inputs = []
        return store.put_json(
            payload,
            PutOptions(
                kind="vector_memory.bundle",
                media_type="application/json",
                schema=schema,
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    @staticmethod
    def _verify_labels(index: Any, expected_count: int) -> None:
        if index.get_current_count() != expected_count:
            raise ValueError("Vector memory bundle keys do not match the native index row count")
        labels = [int(label) for label in index.get_ids_list()]
        if len(labels) != expected_count or set(labels) != set(range(expected_count)):
            raise ValueError("Vector memory native labels do not match the bundle keys")

    @staticmethod
    def _read_index(
        store: ArtifactStore,
        ref: ArtifactRef,
        expected_length: int,
        *,
        expected_bytes: bytes | None = None,
        require_selected: bool = True,
    ) -> bytes:
        from polisyos.core.artifacts import artifact_ref_for_manifest, artifact_ref_identity_key
        from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef

        if type(ref) is not CoreArtifactRef or (
            require_selected and ref.manifest_profile_sha256 is None
        ):
            raise ValueError("Vector memory index requires a profile-qualified reference")
        if (ref.kind, ref.media_type) != ("vector_memory.index", "application/octet-stream"):
            raise ValueError("Vector memory index reference kind or media is invalid")
        manifest = store.get_manifest(ref)
        actual = artifact_ref_identity_key(artifact_ref_for_manifest(manifest))
        expected = artifact_ref_identity_key(ref)
        if actual[:3] != expected[:3] or (expected[3] is not None and actual[3] != expected[3]):
            raise ValueError("Vector memory index selected manifest does not match reference")
        index_bytes = store.get_bytes(ref)
        if (
            len(index_bytes) != expected_length
            or manifest.byte_size != expected_length
            or hashlib.sha256(index_bytes).hexdigest() != ref.artifact_id.hex
            or (expected_bytes is not None and index_bytes != expected_bytes)
        ):
            raise ValueError("Vector memory index bytes do not match the selected reference")
        return index_bytes

    @staticmethod
    def _read_rows(store: ArtifactStore, ref: ArtifactRef, expected_length: int) -> bytes:
        """Read and verify the exact selected NPZ member within explicit byte ceilings."""
        from polisyos.core.artifacts import artifact_manifest_profile_sha256
        from polisyos.core.artifacts.manifest import (
            ArtifactManifest,
        )
        from polisyos.core.artifacts.manifest import (
            ArtifactRef as CoreArtifactRef,
        )

        if (
            type(ref) is not CoreArtifactRef
            or ref.manifest_profile_sha256 is None
            or (ref.kind, ref.media_type) != ("vector_memory.vectors", "application/x-npz")
        ):
            raise ValueError("vector_memory_rows_ref_invalid")
        if type(expected_length) is not int or not 0 < expected_length <= _MAX_ROWS_BYTES:
            raise ValueError("vector_memory_rows_byte_limit")
        reader = _bounded_reader(store)
        manifest_bytes = reader.get_raw_manifest_bytes_bounded(
            ref, max_manifest_bytes=_MAX_MANIFEST_BYTES
        )
        manifest = ArtifactManifest.model_validate_json(manifest_bytes)
        if (
            manifest.artifact_id != ref.artifact_id
            or manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
            or manifest.byte_size != expected_length
            or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
        ):
            raise ValueError("vector_memory_rows_manifest_mismatch")
        data = bytearray()
        with reader.open_member_bounded(
            ref,
            "blob",
            max_manifest_bytes=_MAX_MANIFEST_BYTES,
            expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            max_member_bytes=_MAX_ROWS_BYTES,
        ) as member:
            if member.member_size_bytes != expected_length:
                raise ValueError("vector_memory_rows_byte_length_mismatch")
            while len(data) < expected_length:
                remaining = expected_length - len(data)
                chunk = member.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("vector_memory_rows_truncated")
                if type(chunk) is not bytes or len(chunk) > remaining:
                    raise ValueError("vector_memory_rows_stream_contract_invalid")
                data.extend(chunk)
            if member.read(1):
                raise ValueError("vector_memory_rows_trailing_bytes")
        if (
            not member.payload_integrity_verified
            or hashlib.sha256(data).hexdigest() != ref.artifact_id.hex
        ):
            raise ValueError("vector_memory_rows_integrity_failed")
        return bytes(data)

    def load_from_artifact(
        self,
        store: ArtifactStore,
        ref: ArtifactRef,
        *,
        allow_trusted_native: bool = False,
    ) -> None:
        """Validate a complete bundle before atomically publishing its generation.

        Row bundles are bounded and rebuilt without reading an external graph.
        Legacy native bundles require externally established trusted input and an
        explicit opt-in; their original selected profile may remain unestablished.
        """
        from polisyos.core.artifacts import (
            CoreJsonReadLimits,
            input_ref_from_artifact_ref,
            load_core_json_artifact,
            read_core_json_artifact_bounded,
        )
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef

        if type(ref) is not CoreArtifactRef or (ref.kind, ref.media_type) != (
            "vector_memory.bundle",
            "application/json",
        ):
            raise ValueError("Vector memory bundle reference kind or media is invalid")
        if type(allow_trusted_native) is not bool:
            raise TypeError("allow_trusted_native must be a boolean")
        if not allow_trusted_native:
            if ref.manifest_profile_sha256 is None:
                raise UntrustedNativeVectorBundleError("unprofiled_bundle_not_admitted")
            bounded = read_core_json_artifact_bounded(
                _bounded_reader(store),
                ref,
                limits=CoreJsonReadLimits(
                    max_bytes=_MAX_JSON_BYTES,
                    max_depth=32,
                    max_elements=100_000,
                    max_manifest_bytes=_MAX_MANIFEST_BYTES,
                ),
            )
            bundle_manifest = bounded.manifest
            if bundle_manifest.artifact_schema is None or (
                bundle_manifest.artifact_schema.name,
                bundle_manifest.artifact_schema.version,
            ) != ("polisyos.scientist.VectorMemoryBundle", "3.0"):
                schema = bundle_manifest.artifact_schema
                if schema is None:
                    reason = "unversioned_bundle_not_admitted"
                elif (schema.name, schema.version) == (
                    "polisyos.scientist.VectorMemoryBundle",
                    "2.0",
                ):
                    reason = "legacy_native_index_not_admitted"
                else:
                    reason = "unsupported_vector_bundle_format"
                raise UntrustedNativeVectorBundleError(reason)
            bundle = bounded.value
        else:
            bundle_manifest = store.get_manifest(ref)
            bundle = load_core_json_artifact(store, ref)
        if (bundle_manifest.kind, bundle_manifest.media_type) != (
            "vector_memory.bundle",
            "application/json",
        ):
            raise ValueError("Vector memory bundle manifest kind or media is invalid")
        if type(bundle) is not dict:
            raise ValueError("Vector memory bundle must be a canonical object")

        configuration: dict[str, int] = {}
        for field in ("dim", "max_elements", "ef_construction", "M"):
            value = bundle.get(field)
            if type(value) is not int or value <= 0:
                raise ValueError(f"Vector memory bundle {field} must be a positive integer")
            configuration[field] = value
        dim = configuration["dim"]
        max_elements = configuration["max_elements"]
        ef_construction = configuration["ef_construction"]
        M = configuration["M"]

        keys = bundle.get("keys")
        metadata = bundle.get("metadata")
        if type(keys) is not list or type(metadata) is not list:
            raise ValueError("Vector memory bundle keys and metadata must be lists")
        if len(keys) != len(metadata):
            raise ValueError("Vector memory bundle keys and metadata lengths differ")
        if any(type(key) is not str for key in keys):
            raise ValueError("Vector memory bundle keys must be built-in strings")
        candidate_keys = list(keys)
        if len(set(candidate_keys)) != len(candidate_keys):
            raise ValueError("Vector memory bundle keys must be unique")
        candidate_metadata = [_owned_metadata(row) for row in metadata]
        candidate_key_to_idx = {key: index for index, key in enumerate(candidate_keys)}

        version = bundle.get("schema_version")
        if version == _BUNDLE_ROWS:
            from polisyos.foundry.execute import read_numeric_npz_bounded

            if ref.manifest_profile_sha256 is None:
                raise ValueError("vector_memory_rows_bundle_profile_required")
            schema = bundle_manifest.artifact_schema
            if schema is None or (schema.name, schema.version) != (
                "polisyos.scientist.VectorMemoryBundle",
                "3.0",
            ):
                raise ValueError("vector_memory_rows_bundle_schema_mismatch")
            if "index_ref" in bundle or "index_artifact_id" in bundle:
                raise ValueError("vector_memory_rows_native_selector_forbidden")
            _require_row_resource_bounds(
                dim=dim, capacity=max_elements, count=len(candidate_keys), M=M, ef=ef_construction
            )
            _require_row_metadata_bounds(tuple(candidate_keys), tuple(candidate_metadata))
            if any(not key or len(key.encode("utf-8")) > 1024 for key in candidate_keys):
                raise ValueError("vector_memory_row_key_limit")
            raw_ref = bundle.get("vectors_ref")
            if type(raw_ref) is not dict:
                raise ValueError("vector_memory_rows_ref_invalid")
            rows_ref = CoreArtifactRef.model_validate(raw_ref)
            edge = input_ref_from_artifact_ref(rows_ref, role=_ROWS_ROLE)
            if [item for item in bundle_manifest.inputs if item.role == _ROWS_ROLE] != [edge]:
                raise ValueError("vector_memory_rows_lineage_mismatch")
            data = self._read_rows(store, rows_ref, bundle.get("vectors_bytes_len"))
            (matrix,) = read_numeric_npz_bounded(
                data,
                names=("vectors",),
                max_entries=1,
                max_elements=_MAX_ROWS_ELEMENTS,
                max_member_bytes=_MAX_ROWS_BYTES,
                ndim=2,
                allow_empty=True,
                exact_dtype="<f4",
            )
            if matrix.shape != (len(candidate_keys), dim):
                raise ValueError("vector_memory_rows_shape_mismatch")
            if not _HAS_HNSW:
                raise ImportError("hnswlib is required to rebuild vector memory rows")
            candidate_index = hnswlib.Index(space="cosine", dim=dim)
            candidate_index.init_index(
                max_elements=max_elements, ef_construction=ef_construction, M=M
            )
            candidate_index.set_ef(50)
            for idx, row in enumerate(matrix):
                candidate_index.add_items([_owned_vector(row)], [idx])
            self._verify_labels(candidate_index, len(candidate_keys))
            candidate = _Generation(
                dim,
                max_elements,
                ef_construction,
                M,
                candidate_index,
                tuple(candidate_keys),
                tuple(candidate_metadata),
                candidate_key_to_idx,
                "rows_selected",
            )
            with self._generation_lock:
                self._generation = candidate
            return
        if not allow_trusted_native:
            raise UntrustedNativeVectorBundleError("unsupported_vector_bundle_format")

        index_bytes_len = bundle.get("index_bytes_len")
        if type(index_bytes_len) is not int or index_bytes_len < 0:
            raise ValueError("Vector memory bundle index_bytes_len must be a non-negative integer")
        version = bundle.get("schema_version")
        if version is None:
            index_id = bundle.get("index_artifact_id")
            if type(index_id) is not str:
                raise ValueError("Vector memory legacy index_artifact_id must be a string")
            legacy_manifest = store.get_manifest(ArtifactID.model_validate(index_id))
            index_ref = CoreArtifactRef(
                artifact_id=legacy_manifest.artifact_id,
                kind=legacy_manifest.kind,
                media_type=legacy_manifest.media_type,
            )
            binding_status: IndexBindingStatus = "legacy_default_at_read"
        elif version == _BUNDLE_V2:
            schema = bundle_manifest.artifact_schema
            if schema is None or (schema.name, schema.version) != (
                "polisyos.scientist.VectorMemoryBundle",
                "2.0",
            ):
                raise ValueError("Vector memory bundle schema does not match v2")
            if "index_artifact_id" in bundle:
                raise ValueError("Vector memory v2 bundle must not contain a legacy index selector")
            raw_ref = bundle.get("index_ref")
            if type(raw_ref) is not dict:
                raise ValueError("Vector memory bundle index_ref must be an object")
            index_ref = CoreArtifactRef.model_validate(raw_ref)
            edge = input_ref_from_artifact_ref(index_ref, role=_INDEX_ROLE)
            if [item for item in bundle_manifest.inputs if item.role == _INDEX_ROLE] != [edge]:
                raise ValueError("Vector memory bundle index lineage does not match selected view")
            binding_status = "exact_selected"
        else:
            raise ValueError("Vector memory bundle schema version is unsupported")
        index_bytes = self._read_index(
            store, index_ref, index_bytes_len, require_selected=version is not None
        )

        _validate_native_index_bytes(
            index_bytes,
            dim=dim,
            max_elements=max_elements,
            ef_construction=ef_construction,
            M=M,
            count=len(candidate_keys),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            index_path.write_bytes(index_bytes)
            candidate_index = hnswlib.Index(space="cosine", dim=dim)
            candidate_index.load_index(str(index_path), max_elements=max_elements)
            candidate_index.set_ef(50)

        self._verify_labels(candidate_index, len(candidate_keys))
        if candidate_index.get_max_elements() != max_elements:
            raise ValueError("Vector memory bundle capacity does not match the native index")

        candidate = _Generation(
            dim,
            max_elements,
            ef_construction,
            M,
            candidate_index,
            tuple(candidate_keys),
            tuple(candidate_metadata),
            candidate_key_to_idx,
            binding_status,
        )
        with self._generation_lock:
            self._generation = candidate  # publish_native
