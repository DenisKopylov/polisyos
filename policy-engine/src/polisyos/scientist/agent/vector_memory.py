"""HNSW-backed vector memory for fast nearest-neighbor recall.

Uses ``hnswlib`` (already a project dependency) for approximate nearest
neighbor search.  Supports CAS persistence via ``save_to_artifact`` /
``load_from_artifact``.
"""

from __future__ import annotations

import logging
import math
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

try:
    import hnswlib

    _HAS_HNSW = True
except ImportError:
    _HAS_HNSW = False

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore

_logger = logging.getLogger(__name__)


class VectorMemoryStore:
    """HNSW-backed vector memory for fast nearest-neighbor recall.

    Parameters
    ----------
    dim:
        Embedding dimensionality.
    max_elements:
        Maximum number of elements in the index.
    ef_construction:
        HNSW construction parameter (higher = better quality, slower build).
    M:
        HNSW parameter controlling connectivity.
    """

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
        self._dim = dim
        self._max_elements = max_elements
        self._ef_construction = ef_construction
        self._M = M
        self._generation_lock = RLock()

        self._index = self._new_index()

        self._keys: list[str] = []
        self._metadata: list[dict[str, Any]] = []
        self._key_to_idx: dict[str, int] = {}

    @property
    def dim(self) -> int:
        return self._dim

    def __len__(self) -> int:
        with self._generation_lock:
            return len(self._keys)

    def _new_index(self) -> Any:
        """Create an empty native index for the current configuration."""
        index = hnswlib.Index(space="cosine", dim=self._dim)
        index.init_index(
            max_elements=self._max_elements,
            ef_construction=self._ef_construction,
            M=self._M,
        )
        index.set_ef(50)
        return index

    def _save_index_bytes(self) -> bytes:
        """Capture the current native generation before a mutating operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            self._index.save_index(str(index_path))
            return index_path.read_bytes()

    def _restore_index_bytes(self, index_bytes: bytes) -> None:
        """Restore a previously captured native generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            index_path.write_bytes(index_bytes)
            restored = hnswlib.Index(space="cosine", dim=self._dim)
            restored.load_index(str(index_path), max_elements=self._max_elements)
            restored.set_ef(50)
        self._index = restored

    def add(self, key: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        """Add a vector with associated key and metadata.

        If the key already exists, it is overwritten.
        """
        with self._generation_lock:
            self._add(key, embedding, deepcopy(metadata) if metadata is not None else {})

    def _add(self, key: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        """Mutate one native generation while its readers are excluded."""
        if not isinstance(key, str) or not key:
            raise ValueError("Vector memory key must be a non-empty string")
        if not isinstance(metadata, dict):
            raise ValueError("Vector memory metadata must be an object")
        if len(embedding) != self._dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._dim}, got {len(embedding)}"
            )
        if not all(math.isfinite(float(value)) for value in embedding):
            raise ValueError("Vector memory embedding must contain finite values")

        idx = self._key_to_idx.get(key)
        if idx is not None:
            # Overwrite existing
            snapshot = self._save_index_bytes()
            try:
                self._index.add_items([embedding], [idx])
            except Exception:
                self._restore_index_bytes(snapshot)
                raise
            self._metadata[idx] = metadata
            return

        if len(self._keys) >= self._max_elements:
            raise RuntimeError(
                "Vector memory capacity exhausted; resize before adding another element"
            )

        idx = len(self._keys)
        snapshot = self._save_index_bytes() if self._keys else None
        try:
            self._index.add_items([embedding], [idx])
        except Exception:
            if snapshot is None:
                self._index = self._new_index()
            else:
                self._restore_index_bytes(snapshot)
            raise
        self._keys.append(key)
        self._metadata.append(metadata)
        self._key_to_idx[key] = idx

    def query(
        self,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Query nearest neighbors.

        Parameters
        ----------
        embedding:
            Query vector.
        top_k:
            Number of results to return.

        Returns
        -------
        list of (key, distance, metadata) tuples, sorted by distance ascending.
        """
        with self._generation_lock:
            if len(embedding) != self._dim:
                raise ValueError("Query embedding dimension does not match vector memory")
            if not all(math.isfinite(float(value)) for value in embedding):
                raise ValueError("Query embedding must contain finite values")
            if not self._keys or top_k <= 0:
                return []

            effective_k = min(top_k, len(self._keys))
            labels, distances = self._index.knn_query([embedding], k=effective_k)

            results: list[tuple[str, float, dict[str, Any]]] = []
            for label, dist in zip(labels[0], distances[0]):
                idx = int(label)
                if 0 <= idx < len(self._keys):
                    results.append((self._keys[idx], float(dist), deepcopy(self._metadata[idx])))
        return results

    def save_to_artifact(self, store: ArtifactStore) -> ArtifactRef:
        """Persist the index + metadata to the artifact store.

        Returns
        -------
        ArtifactRef
            Reference to the persisted index artifact.
        """
        from polisyos.core.artifacts.store import PutOptions

        with self._generation_lock:
            index_bytes = self._save_index_bytes()
            payload = {
                "dim": self._dim,
                "max_elements": self._max_elements,
                "ef_construction": self._ef_construction,
                "M": self._M,
                "keys": list(self._keys),
                "metadata": deepcopy(self._metadata),
                "index_bytes_len": len(index_bytes),
            }

        # Store index as raw bytes
        index_ref = store.put_bytes(
            index_bytes,
            PutOptions(kind="vector_memory.index", media_type="application/octet-stream"),
        )

        # Return a composite reference (metadata contains the index ref)
        payload["index_artifact_id"] = index_ref.artifact_id
        return store.put_json(
            payload,
            PutOptions(kind="vector_memory.bundle", media_type="application/json"),
        )

    def load_from_artifact(self, store: ArtifactStore, ref: ArtifactRef) -> None:
        """Load the index + metadata from the artifact store."""
        import json

        bundle_bytes = store.get_bytes(ref.artifact_id)
        bundle = json.loads(bundle_bytes)

        dim = int(bundle["dim"])
        max_elements = int(bundle["max_elements"])
        ef_construction = int(bundle["ef_construction"])
        M = int(bundle["M"])
        keys = bundle["keys"]
        metadata = bundle["metadata"]
        if not isinstance(keys, list) or not isinstance(metadata, list):
            raise ValueError("Vector memory bundle keys and metadata must be lists")
        if len(keys) != len(metadata):
            raise ValueError("Vector memory bundle keys and metadata lengths differ")
        if not all(isinstance(key, str) and key for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("Vector memory bundle keys must be unique non-empty strings")
        if not all(isinstance(item, dict) for item in metadata):
            raise ValueError("Vector memory bundle metadata entries must be objects")
        if dim <= 0 or max_elements < len(keys) or max_elements <= 0:
            raise ValueError("Vector memory bundle configuration is inconsistent")

        index_artifact_id = bundle["index_artifact_id"]
        index_bytes = store.get_bytes(index_artifact_id)
        if bundle.get("index_bytes_len", len(index_bytes)) != len(index_bytes):
            raise ValueError("Vector memory bundle native byte length differs")

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            index_path.write_bytes(index_bytes)
            candidate_index = hnswlib.Index(space="cosine", dim=dim)
            candidate_index.load_index(
                str(index_path),
                max_elements=max_elements,
            )
            candidate_index.set_ef(50)

        if set(candidate_index.get_ids_list()) != set(range(len(keys))):
            raise ValueError("Vector memory native labels do not match the metadata generation")
        if keys:
            vectors = candidate_index.get_items(list(range(len(keys))))
            if vectors.shape != (len(keys), dim) or not all(
                math.isfinite(float(value)) for vector in vectors for value in vector
            ):
                raise ValueError("Vector memory native vectors do not match the declared dimension")

        # Publish only after every native and metadata check has succeeded.
        with self._generation_lock:
            self._dim = dim
            self._max_elements = max_elements
            self._ef_construction = ef_construction
            self._M = M
            self._keys = list(keys)
            self._metadata = deepcopy(metadata)
            self._key_to_idx = {k: i for i, k in enumerate(self._keys)}
            self._index = candidate_index
