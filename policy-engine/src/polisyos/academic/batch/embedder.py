"""Stage 6: build local embeddings + HNSW index for academic works."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.batch_common.thermal import pause_between_batches
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def build_hnsw_index(
    *,
    db_path: Path,
    index_dir: Path,
    embedding_model: str = "intfloat/multilingual-e5-large",
    embedding_dimension: int = 1024,
    embedding_batch_size: int = 32,
    embedding_device: str = "mps",
    thermal_pause_seconds: float = 0.0,
) -> int:
    """Embed work title+abstract and build HNSW index."""
    import hnswlib
    from sentence_transformers import SentenceTransformer

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("SELECT id, title, abstract FROM ac_works").fetchall()
    finally:
        con.close()

    if not rows:
        return 0

    ids: list[str] = []
    texts: list[str] = []
    for row in rows:
        ids.append(row[0])
        title = row[1] or ""
        abstract = (row[2] or "")[:1200]
        texts.append(f"{title}. {abstract}".strip())

    model = SentenceTransformer(embedding_model, device=embedding_device)

    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), embedding_batch_size):
        stop = min(start + embedding_batch_size, len(texts))
        vec = model.encode(
            texts[start:stop],
            batch_size=min(embedding_batch_size, stop - start),
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        chunks.append(vec.astype(np.float32))
        pause_between_batches(thermal_pause_seconds)

    embeddings = np.vstack(chunks)
    dim = embeddings.shape[1] if embeddings.size else embedding_dimension

    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=len(embeddings), ef_construction=200, M=16)
    int_ids = np.arange(len(ids))
    index.add_items(embeddings, int_ids)

    npz_path = index_dir / "ac_work_embeddings.npz"
    hnsw_path = index_dir / "ac_work_index.hnsw"
    np.savez(str(npz_path), ids=np.array(ids, dtype=object), vectors=embeddings)
    index.save_index(str(hnsw_path))

    logger.info("Academic embeddings complete: %d vectors", len(ids))
    return len(ids)


def run_embed(config: AcademicBatchConfig, *, thermal: bool = False) -> int:
    started_at = datetime.now(UTC).isoformat()
    pause_s = 0.5 if thermal else 0.0
    count = build_hnsw_index(
        db_path=config.db_path,
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_dimension=config.embedding_dimension,
        embedding_batch_size=config.embedding_batch_size,
        embedding_device=config.embedding_device,
        thermal_pause_seconds=pause_s,
    )
    write_stage_manifest(
        manifest_path=config.manifests_dir / "embed.json",
        stage="embed",
        status="ok",
        metrics={"embedded": count, "thermal": thermal},
        artifacts=[config.index_dir / "ac_work_embeddings.npz", config.index_dir / "ac_work_index.hnsw"],
        started_at=started_at,
    )
    return count
