"""Native HNSW discovery with indivisible immutable memory generations.

CAS composite references identify persisted generations. Writers prepare a
private native index and publish one pointer; each query captures it once.
This is an in-process contract, not distributed publication.
"""

from __future__ import annotations

import hashlib
import math
import struct
import tempfile
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from polisyos.core import artifacts, canon

try:
    import hnswlib

    _HAS_HNSW = True
except ImportError:
    _HAS_HNSW = False

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class _VectorGeneration:
    dim: int
    max_elements: int
    ef_construction: int
    M: int
    index: Any
    keys: tuple[str, ...]
    metadata: tuple[bytes, ...]
    key_to_idx: Mapping[str, int]
    ref_identity: tuple[str, str, str, str | None] | None
    version: int


class VectorMemoryStore:
    """Discover neighbors from one captured immutable native generation.

    Args:
        dim: Embedding dimension.
        max_elements: Explicit native capacity.
        ef_construction: HNSW construction quality parameter.
        M: Native graph connectivity parameter.
    """

    def __init__(
        self, dim: int = 384, max_elements: int = 100_000, ef_construction: int = 200, M: int = 16
    ) -> None:
        if not _HAS_HNSW:
            raise ImportError("hnswlib is required for VectorMemoryStore")
        for name, value in (
            ("dim", dim),
            ("max_elements", max_elements),
            ("ef_construction", ef_construction),
            ("M", M),
        ):
            self._positive_integer(value, name)
        self._writer_lock = RLock()
        self._generation = _VectorGeneration(
            dim,
            max_elements,
            ef_construction,
            M,
            self._new_index(dim, max_elements, ef_construction, M),
            (),
            (),
            MappingProxyType({}),
            None,
            0,
        )

    @staticmethod
    def _positive_integer(value: Any, name: str) -> int:
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    @property
    def dim(self) -> int:
        """Return the dimension of the currently published generation."""
        return self._generation.dim

    def __len__(self) -> int:
        return len(self._generation.keys)

    @staticmethod
    def _new_index(dim: int, capacity: int, construction: int, M: int) -> Any:
        index = hnswlib.Index(space="cosine", dim=dim)
        index.init_index(max_elements=capacity, ef_construction=construction, M=M)
        index.set_ef(50)
        return index

    @staticmethod
    def _index_bytes(index: Any) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "hnsw.index"
            index.save_index(str(path))
            return path.read_bytes()

    @staticmethod
    def _load_index(data: bytes, dim: int, capacity: int) -> Any:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "hnsw.index"
            path.write_bytes(data)
            index = hnswlib.Index(space="cosine", dim=dim)
            index.load_index(str(path), max_elements=capacity)
            index.set_ef(50)
        return index

    @staticmethod
    def _admit_native_header(data: bytes, dim: int, capacity: int, count: int) -> None:
        """Admit the pinned hnswlib 0.8 native ABI before its unchecked loader.

        The native file has no dimension field. Its physical float stride is
        encoded by the label/data offsets; Index.dim only echoes its constructor.
        These files remain native-ABI artifacts, not portable interchange data.
        """
        if version("hnswlib") != "0.8.0":
            raise ValueError("Unsupported native HNSW format: requires hnswlib 0.8.0")
        header = struct.Struct("@6N")
        if len(data) < header.size:
            raise ValueError("Truncated native HNSW header")
        _, native_capacity, native_count, record_size, label_offset, data_offset = (
            header.unpack_from(data)
        )
        if (
            native_capacity != capacity
            or native_count != count
            or label_offset - data_offset != dim * struct.calcsize("@f")
            or data_offset >= label_offset
            or record_size < label_offset + struct.calcsize("@N")
        ):
            raise ValueError("Native HNSW dimension/count/capacity disagrees with the bundle")

    @staticmethod
    def _embedding(embedding: list[float], dim: int) -> list[float]:
        if len(embedding) != dim:
            raise ValueError(f"Embedding dimension mismatch: expected {dim}, got {len(embedding)}")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in embedding):
            raise ValueError("Embedding must contain finite numbers")
        return list(embedding)

    def add(self, key: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        """Prepare add/update privately, then publish one complete generation."""
        if not isinstance(key, str) or not key:
            raise ValueError("Vector key must be a non-empty string")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("Vector metadata must be an object")
        encoded = canon.to_canonical_bytes(metadata or {}, canon.CanonSpec(forbid_floats=False))
        with self._writer_lock:
            previous = self._generation
            vector = self._embedding(embedding, previous.dim)
            position = previous.key_to_idx.get(key)
            if position is None and len(previous.keys) >= previous.max_elements:
                raise RuntimeError("Vector memory capacity exhausted")
            candidate = (
                self._load_index(
                    self._index_bytes(previous.index), previous.dim, previous.max_elements
                )
                if previous.keys
                else self._new_index(
                    previous.dim, previous.max_elements, previous.ef_construction, previous.M
                )
            )
            position = len(previous.keys) if position is None else position
            candidate.add_items([vector], [position])
            keys, records = list(previous.keys), list(previous.metadata)
            if position == len(keys):
                keys.append(key)
                records.append(encoded)
            else:
                records[position] = encoded
            self._generation = _VectorGeneration(
                previous.dim,
                previous.max_elements,
                previous.ef_construction,
                previous.M,
                candidate,
                tuple(keys),
                tuple(records),
                MappingProxyType({name: i for i, name in enumerate(keys)}),
                None,
                previous.version + 1,
            )

    def metadata_for_key(self, key: str) -> dict[str, Any] | None:
        """Read an exact known key without geometric discovery."""
        generation = self._generation
        position = generation.key_to_idx.get(key)
        return (
            None if position is None else canon.from_canonical_bytes(generation.metadata[position])
        )

    def query(
        self, embedding: list[float], top_k: int = 10
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Return key/distance/copied metadata from one captured native generation."""
        generation = self._generation
        vector = self._embedding(embedding, generation.dim)
        if type(top_k) is not int or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if not generation.keys:
            return []
        labels, distances = generation.index.knn_query([vector], k=min(top_k, len(generation.keys)))
        return [
            (
                generation.keys[int(label)],
                float(distance),
                canon.from_canonical_bytes(generation.metadata[int(label)]),
            )
            for label, distance in zip(labels[0], distances[0])
        ]

    def save_to_artifact(self, store: artifacts.ArtifactStore) -> artifacts.ArtifactRef:
        """Persist one captured composite generation without a latest pointer."""
        generation = self._generation
        index_ref = store.put_bytes(
            self._index_bytes(generation.index),
            artifacts.PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        )
        payload = {
            "schema_version": "2.0",
            "dim": generation.dim,
            "max_elements": generation.max_elements,
            "ef_construction": generation.ef_construction,
            "M": generation.M,
            "keys": list(generation.keys),
            "metadata": [canon.from_canonical_bytes(row) for row in generation.metadata],
            "index_ref": index_ref.model_dump(mode="json"),
        }
        return store.put_json(
            payload,
            artifacts.PutOptions(kind="vector_memory.bundle", media_type="application/json"),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )

    def load_from_artifact(
        self, store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef
    ) -> None:
        """Load privately; any failure leaves the published generation unchanged."""
        if ref.kind != "vector_memory.bundle" or ref.media_type != "application/json":
            raise ValueError("Vector bundle reference has the wrong type")
        bundle = canon.from_canonical_bytes(self._artifact_bytes(store, ref))
        if not isinstance(bundle, dict):
            raise ValueError("Vector bundle must be an object")
        if "schema_version" in bundle:
            if bundle["schema_version"] != "2.0" or "index_artifact_id" in bundle:
                raise ValueError("Unsupported vector bundle schema")
            if "index_ref" not in bundle:
                raise ValueError("Vector bundle v2 requires a complete native reference")
        elif "index_artifact_id" not in bundle or "index_ref" in bundle:
            raise ValueError("Legacy vector bundle requires its original index address")
        dim = self._positive_integer(bundle["dim"], "dim")
        capacity = self._positive_integer(bundle["max_elements"], "max_elements")
        construction = self._positive_integer(bundle["ef_construction"], "ef_construction")
        M = self._positive_integer(bundle["M"], "M")
        keys, metadata = bundle["keys"], bundle["metadata"]
        if (
            not isinstance(keys, list)
            or not isinstance(metadata, list)
            or len(keys) != len(metadata)
            or len(keys) > capacity
            or any(not isinstance(k, str) or not k for k in keys)
            or len(set(keys)) != len(keys)
            or any(not isinstance(row, dict) for row in metadata)
        ):
            raise ValueError("Vector keys/metadata must describe one complete unique generation")
        if "index_ref" in bundle:
            index_ref = artifacts.ArtifactRef.model_validate(bundle["index_ref"])
        else:
            index_ref = artifacts.ArtifactRef(
                artifact_id=bundle["index_artifact_id"],
                kind="vector_memory.index",
                media_type="application/octet-stream",
            )
        if (
            index_ref.kind != "vector_memory.index"
            or index_ref.media_type != "application/octet-stream"
        ):
            raise ValueError("Vector native reference has the wrong type")
        native_bytes = self._artifact_bytes(store, index_ref)
        self._admit_native_header(native_bytes, dim, capacity, len(keys))
        candidate = self._load_index(native_bytes, dim, capacity)
        if candidate.get_current_count() != len(keys) or set(candidate.get_ids_list()) != set(
            range(len(keys))
        ):
            raise ValueError("Native labels and vector keys differ")
        records = tuple(
            canon.to_canonical_bytes(row, canon.CanonSpec(forbid_floats=False)) for row in metadata
        )
        with self._writer_lock:
            self._generation = _VectorGeneration(
                dim,
                capacity,
                construction,
                M,
                candidate,
                tuple(keys),
                records,
                MappingProxyType({key: i for i, key in enumerate(keys)}),
                artifacts.artifact_ref_identity_key(ref),
                self._generation.version + 1,
            )

    @staticmethod
    def _artifact_bytes(store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef) -> bytes:
        """Consume the existing owned snapshot port when the backend supplies it."""
        reader = getattr(store, "get_verified_snapshot", None)
        if callable(reader):
            snapshot = reader(ref)
            manifest = snapshot.manifest
            if (
                manifest.artifact_id != ref.artifact_id
                or manifest.kind != ref.kind
                or manifest.media_type != ref.media_type
            ):
                raise ValueError("Vector artifact snapshot does not match its typed reference")
            data = snapshot.data
        else:
            # Exact bytes remain checked for legacy providers. This fallback
            # does not establish an owned immutable byte/manifest snapshot.
            data = store.get_bytes(ref)
        if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != ref.artifact_id.hex:
            raise ValueError("Vector artifact bytes do not match the exact content reference")
        return data
