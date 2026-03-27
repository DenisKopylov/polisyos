"""HNSW-backed vector memory for fast nearest-neighbor recall.

Uses ``hnswlib`` (already a project dependency) for approximate nearest
neighbor search.  Supports CAS persistence via ``save_to_artifact`` /
``load_from_artifact``.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
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
        M: int = 16,  # noqa: N803
    ) -> None:
        if not _HAS_HNSW:
            raise ImportError(
                "hnswlib is required for VectorMemoryStore.  "
                "Install it with: pip install hnswlib"
            )
        self._dim = dim
        self._max_elements = max_elements
        self._ef_construction = ef_construction
        self._M = M

        self._index = hnswlib.Index(space="cosine", dim=dim)
        self._index.init_index(
            max_elements=max_elements,
            ef_construction=ef_construction,
            M=M,
        )
        self._index.set_ef(50)

        self._keys: list[str] = []
        self._metadata: list[dict[str, Any]] = []
        self._key_to_idx: dict[str, int] = {}

    @property
    def dim(self) -> int:
        return self._dim

    def __len__(self) -> int:
        return len(self._keys)

    def add(self, key: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        """Add a vector with associated key and metadata.

        If the key already exists, it is overwritten.
        """
        if len(embedding) != self._dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._dim}, got {len(embedding)}"
            )

        idx = self._key_to_idx.get(key)
        if idx is not None:
            # Overwrite existing
            self._metadata[idx] = metadata or {}
            self._index.add_items([embedding], [idx])
            return

        idx = len(self._keys)
        self._keys.append(key)
        self._metadata.append(metadata or {})
        self._key_to_idx[key] = idx
        self._index.add_items([embedding], [idx])

    def query(
        self, embedding: list[float], top_k: int = 10,
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
        if len(self._keys) == 0:
            return []

        effective_k = min(top_k, len(self._keys))
        labels, distances = self._index.knn_query([embedding], k=effective_k)

        results: list[tuple[str, float, dict[str, Any]]] = []
        for label, dist in zip(labels[0], distances[0]):
            idx = int(label)
            if 0 <= idx < len(self._keys):
                results.append((self._keys[idx], float(dist), self._metadata[idx]))
        return results

    def save_to_artifact(self, store: "ArtifactStore") -> "ArtifactRef":
        """Persist the index + metadata to the artifact store.

        Returns
        -------
        ArtifactRef
            Reference to the persisted index artifact.
        """
        from polisyos.core.artifacts.store import PutOptions

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            self._index.save_index(str(index_path))
            index_bytes = index_path.read_bytes()

        payload = {
            "dim": self._dim,
            "max_elements": self._max_elements,
            "ef_construction": self._ef_construction,
            "M": self._M,
            "keys": self._keys,
            "metadata": self._metadata,
            "index_bytes_len": len(index_bytes),
        }

        # Store metadata as JSON
        meta_ref = store.put_json(
            payload,
            PutOptions(kind="vector_memory.meta", media_type="application/json"),
        )

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

    def load_from_artifact(self, store: "ArtifactStore", ref: "ArtifactRef") -> None:
        """Load the index + metadata from the artifact store."""
        import json

        bundle_bytes = store.get_bytes(ref.artifact_id)
        bundle = json.loads(bundle_bytes)

        self._dim = bundle["dim"]
        self._max_elements = bundle["max_elements"]
        self._ef_construction = bundle["ef_construction"]
        self._M = bundle["M"]
        self._keys = bundle["keys"]
        self._metadata = bundle["metadata"]
        self._key_to_idx = {k: i for i, k in enumerate(self._keys)}

        # Load HNSW index
        index_artifact_id = bundle["index_artifact_id"]
        index_bytes = store.get_bytes(index_artifact_id)

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "hnsw.index"
            index_path.write_bytes(index_bytes)
            self._index = hnswlib.Index(space="cosine", dim=self._dim)
            self._index.load_index(
                str(index_path),
                max_elements=self._max_elements,
            )
            self._index.set_ef(50)
