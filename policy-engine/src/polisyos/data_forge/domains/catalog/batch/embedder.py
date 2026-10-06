"""Stage 6: Build local embeddings and HNSW index for datasets."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.knowledge.embedding_projection import (
    dataset_embedding_text,
)
from polisyos.data_forge.kernel.embeddings import (
    build_embedding_generation,
    derive_encoder_identity,
    embedding_generation_manifest,
)
from polisyos.data_forge.kernel.io.generation_basis import GenerationIdentity
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig

logger = get_logger(__name__)


def _encoder_cache_key(config: DatasetBatchConfig) -> tuple[str, str]:
    return config.embedding_model, config.resolved_embedding_device


def _cached_encoder(
    config: DatasetBatchConfig,
) -> tuple[object, GenerationIdentity] | None:
    cached = getattr(config, "_catalog_embedding_encoder", None)
    if not isinstance(cached, tuple) or len(cached) != 3:
        return None
    key, encoder, identity = cached
    if key != _encoder_cache_key(config) or not isinstance(identity, GenerationIdentity):
        return None
    return encoder, identity


def _load_encoder(
    config: DatasetBatchConfig, *, local_only: bool, refresh: bool = False
) -> tuple[object, GenerationIdentity] | None:
    """Resolve one live encoder and bind its weights and tokenizer assets.

    Resume checks are local-only: they never turn a cache lookup into a model
    download. A normal embed run keeps the existing SentenceTransformer
    resolution behavior and caches the exact object used to produce vectors.
    """
    if not refresh:
        cached = _cached_encoder(config)
        if cached is not None:
            return cached
    model_reference = config.embedding_model
    if local_only:
        local_path = Path(model_reference).expanduser()
        if local_path.exists():
            model_reference = str(local_path.resolve())
        else:
            try:
                from huggingface_hub import snapshot_download

                model_reference = snapshot_download(
                    repo_id=model_reference,
                    local_files_only=True,
                )
            except Exception:
                return None
    try:
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(
            model_reference,
            device=config.resolved_embedding_device,
        )
        identity = derive_encoder_identity(encoder)
    except Exception:
        if local_only:
            return None
        raise
    config._catalog_embedding_encoder = _encoder_cache_key(config), encoder, identity
    return encoder, identity


def _encoder_identity_for_resume(
    config: DatasetBatchConfig,
) -> tuple[str | None, str]:
    """Return the current encoder identity only when its live assets resolve."""
    try:
        with duckdb.connect(str(config.db_path), read_only=True) as con:
            table = con.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'ds_datasets'"
            ).fetchone()
            if table is None:
                return None, "not_established"
            count = int(con.execute("SELECT count(*) FROM ds_datasets").fetchone()[0] or 0)
    except (duckdb.Error, OSError):
        return None, "not_established"
    if count == 0:
        return None, "not_required_empty"
    loaded = _load_encoder(config, local_only=True, refresh=True)
    if loaded is None:
        return None, "not_established"
    _encoder, identity = loaded
    return identity.content_identity, "established"


def build_hnsw_index(
    *,
    db_path: Path,
    index_dir: Path,
    embedding_model: str = "intfloat/multilingual-e5-large",
    embedding_dimension: int = 1024,
    embedding_batch_size: int = 32,
    embedding_device: str = "cpu",
    thermal_pause_seconds: float = 0.0,
    encoder: object | None = None,
) -> int:
    """Embed datasets and build one HNSW index."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT id, title, description, keywords, variables FROM ds_datasets"
        ).fetchall()
    finally:
        con.close()

    prepared_rows = [(row[0], dataset_embedding_text(row)) for row in rows]

    count, _dimension = build_embedding_generation(
        rows=prepared_rows,
        index_dir=index_dir,
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        embedding_dimension=embedding_dimension,
        embedding_batch_size=embedding_batch_size,
        thermal_pause_seconds=thermal_pause_seconds,
        encoder=encoder,
        basis_kind="catalog_dataset_embedding",
        projection_rule_version="policyos.catalog_dataset_embedding_projection.v1",
        legacy_embeddings_path=index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=index_dir / "ds_dataset_index.hnsw",
    )
    return count


def run_embed(config: DatasetBatchConfig, *, thermal: bool = False) -> int:
    """Run embed."""
    started_at = datetime.now(UTC).isoformat()
    pause_s = 0.5 if thermal else 0.0
    encoder: object | None = None
    try:
        with duckdb.connect(str(config.db_path), read_only=True) as con:
            has_rows = int(con.execute("SELECT count(*) FROM ds_datasets").fetchone()[0] or 0) > 0
    except (duckdb.Error, OSError):
        has_rows = False
    if has_rows:
        loaded = _load_encoder(config, local_only=False)
        if loaded is not None:
            encoder, _identity = loaded
    count = build_hnsw_index(
        db_path=config.db_path,
        index_dir=config.index_dir,
        embedding_model=config.embedding_model,
        embedding_dimension=config.embedding_dimension,
        embedding_batch_size=config.embedding_batch_size,
        embedding_device=config.resolved_embedding_device,
        thermal_pause_seconds=pause_s,
        encoder=encoder,
    )
    generation = embedding_generation_manifest(
        config.index_dir,
        legacy_embeddings_path=config.index_dir / "ds_dataset_embeddings.npz",
        legacy_index_path=config.index_dir / "ds_dataset_index.hnsw",
    )
    generation_metrics = generation[0] if generation else {}
    generation_artifacts = generation[1] if generation else ()
    write_stage_manifest(
        manifest_path=config.manifests_dir / "embed.json",
        stage="embed",
        status=("empty_generation" if count == 0 else "ok"),
        metrics={
            "embedded": count,
            "thermal": thermal,
            "embedding_generation": generation_metrics,
        },
        artifacts=list(generation_artifacts),
        started_at=started_at,
    )
    logger.info("Dataset embedding complete: %d vectors", count)
    return count
