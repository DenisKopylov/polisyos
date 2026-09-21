"""Shared encode/index mechanics for prepared Data Forge embedding rows."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from polisyos.data_forge.kernel.runtime import pause_between_batches


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
    model = SentenceTransformer(embedding_model, device=embedding_device)

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

    np.savez(str(embeddings_path), ids=np.array(ids, dtype=object), vectors=embeddings)
    index.save_index(str(index_path))
    return len(ids), int(dim)
