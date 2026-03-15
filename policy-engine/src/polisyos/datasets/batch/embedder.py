"""Stage 6: Build local embeddings and HNSW index for datasets."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.batch_common.thermal import pause_between_batches
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.config import DatasetBatchConfig

logger = get_logger(__name__)


def build_hnsw_index(
    *,
    db_path: Path,
    index_dir: Path,
    embedding_model: str = "intfloat/multilingual-e5-large",
    embedding_batch_size: int = 32,
    embedding_device: str = "cpu",
    thermal_pause_seconds: float = 0.0,
) -> int:
    """Embed datasets and build one HNSW index."""
    import hnswlib
    from sentence_transformers import SentenceTransformer

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("SELECT id, title, description, keywords, variables FROM ds_datasets").fetchall()
    finally:
        con.close()

    if not rows:
        return 0

    ids: list[str] = []
    texts: list[str] = []
    for row in rows:
        ids.append(row[0])
        title = row[1] or ""
        desc = (row[2] or "")[:500]
        keywords = list(row[3] or [])
        variables = list(row[4] or [])
        texts.append(f"{title} {desc} {' '.join(keywords[:20])} {' '.join(variables[:20])}".strip())

    model = SentenceTransformer(embedding_model, device=embedding_device)
    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), embedding_batch_size):
        stop = min(start + embedding_batch_size, len(texts))
        chunk = model.encode(
            texts[start:stop],
            batch_size=min(embedding_batch_size, stop - start),
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        chunks.append(chunk.astype(np.float32))
        pause_between_batches(thermal_pause_seconds)

    vectors = np.vstack(chunks) if chunks else np.zeros((0, 1024), dtype=np.float32)
    if len(vectors) == 0:
        return 0

    dim = vectors.shape[1]
    idx = hnswlib.Index(space="cosine", dim=dim)
    idx.init_index(max_elements=len(vectors), ef_construction=200, M=16)
    int_ids = np.arange(len(ids))
    idx.add_items(vectors, int_ids)

    np.savez(str(index_dir / "ds_dataset_embeddings.npz"), ids=np.array(ids, dtype=object), vectors=vectors)
    idx.save_index(str(index_dir / "ds_dataset_index.hnsw"))
    return len(ids)


def run_embed(config: DatasetBatchConfig, *, thermal: bool = False) -> int:
    started_at = datetime.now(UTC).isoformat()
    pause_s = 0.5 if thermal else 0.0
    count = build_hnsw_index(
        db_path=config.db_path,
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_batch_size=config.embedding_batch_size,
        embedding_device=config.resolved_embedding_device,
        thermal_pause_seconds=pause_s,
    )
    write_stage_manifest(
        manifest_path=config.manifests_dir / "embed.json",
        stage="embed",
        status="ok",
        metrics={"embedded": count, "thermal": thermal},
        artifacts=[config.index_dir / "ds_dataset_embeddings.npz", config.index_dir / "ds_dataset_index.hnsw"],
        started_at=started_at,
    )
    logger.info("Dataset embedding complete: %d vectors", count)
    return count
