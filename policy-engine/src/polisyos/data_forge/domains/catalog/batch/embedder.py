"""Stage 6: Build local embeddings and HNSW index for datasets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb

from polisyos.common.logger import get_logger
from polisyos.data_forge.kernel.embeddings import build_embedding_index
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig

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
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT id, title, description, keywords, variables FROM ds_datasets"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        return 0

    prepared_rows: list[tuple[object, str]] = []
    for row in rows:
        title = row[1] or ""
        desc = (row[2] or "")[:500]
        keywords = list(row[3] or [])
        variables = list(row[4] or [])
        prepared_rows.append(
            (
                row[0],
                f"{title} {desc} {' '.join(keywords[:20])} {' '.join(variables[:20])}".strip(),
            )
        )

    count, _dimension = build_embedding_index(
        rows=prepared_rows,
        embeddings_path=index_dir / "ds_dataset_embeddings.npz",
        index_path=index_dir / "ds_dataset_index.hnsw",
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        embedding_batch_size=embedding_batch_size,
        thermal_pause_seconds=thermal_pause_seconds,
    )
    return count


def run_embed(config: DatasetBatchConfig, *, thermal: bool = False) -> int:
    """Run embed."""
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
        artifacts=[
            config.index_dir / "ds_dataset_embeddings.npz",
            config.index_dir / "ds_dataset_index.hnsw",
        ],
        started_at=started_at,
    )
    logger.info("Dataset embedding complete: %d vectors", count)
    return count
