"""Stage 6: build local embeddings + HNSW index for academic works."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb

from polisyos.common.logger import get_logger
from polisyos.data_forge.kernel.embeddings import build_embedding_index
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

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
) -> tuple[int, int]:
    """Embed work title+abstract and build HNSW index."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("SELECT id, title, abstract FROM ac_works").fetchall()
    finally:
        con.close()

    if not rows:
        return 0, int(embedding_dimension)

    prepared_rows: list[tuple[object, str]] = []
    for row in rows:
        title = row[1] or ""
        abstract = (row[2] or "")[:1200]
        prepared_rows.append((row[0], f"{title}. {abstract}".strip()))

    count, dim = build_embedding_index(
        rows=prepared_rows,
        embeddings_path=index_dir / "ac_work_embeddings.npz",
        index_path=index_dir / "ac_work_index.hnsw",
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        embedding_dimension=embedding_dimension,
        embedding_batch_size=embedding_batch_size,
        thermal_pause_seconds=thermal_pause_seconds,
    )

    logger.info("Academic embeddings complete: %d vectors", count)
    return count, dim


def run_embed(config: AcademicBatchConfig, *, thermal: bool = False) -> int:
    """Run embed."""
    started_at = datetime.now(UTC).isoformat()
    pause_s = 0.5 if thermal else 0.0
    count, built_dimension = build_hnsw_index(
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
        metrics={
            "embedded": count,
            "thermal": thermal,
            "embedding_model": config.embedding_model,
            "embedding_dimension": built_dimension,
            "embedding_device": config.embedding_device,
        },
        artifacts=[
            config.index_dir / "ac_work_embeddings.npz",
            config.index_dir / "ac_work_index.hnsw",
        ],
        started_at=started_at,
    )
    return count
