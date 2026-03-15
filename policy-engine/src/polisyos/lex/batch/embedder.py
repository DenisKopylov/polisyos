"""Local sentence-transformers embeddings for Lex graph tables."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import duckdb
import hnswlib
import numpy as np

from polisyos.batch_common.thermal import pause_between_batches
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmbeddingStats:
    entities_embedded: int = 0
    facts_embedded: int = 0
    provisions_embedded: int = 0
    entities_skipped: int = 0
    facts_skipped: int = 0
    provisions_skipped: int = 0
    elapsed_seconds: float = 0.0


def _entity_embedding_text(row: tuple) -> str:
    name_en, name_uk, entity_type, aliases_en, aliases_uk = row
    parts = ["ENTITY", f"en: {name_en}", f"uk: {name_uk or ''}", f"type: {entity_type}"]
    aliases: list[str] = []
    if aliases_en:
        aliases.extend(str(aliases_en).split("; ")[:6])
    if aliases_uk:
        aliases.extend(str(aliases_uk).split("; ")[:6])
    if aliases:
        parts.append("aliases: " + "; ".join(aliases))
    return "\n".join(parts)


def _fact_embedding_text(row: tuple) -> str:
    (
        subject_en,
        subject_uk,
        predicate,
        object_en,
        object_uk,
        fact_text,
        norm_type,
        action_canon,
        norm_type_canon,
        condition_text_uk,
        exception_text_uk,
        procedure_text_uk,
        thresholds_json,
        source_quote_uk,
    ) = row

    parts = [
        "FACT",
        f"norm_type: {norm_type_canon or norm_type or 'unknown'}",
        f"action: {action_canon or predicate or 'unknown'}",
        f"spo: {subject_en} ({subject_uk or ''}) {predicate} {object_en} ({object_uk or ''})",
        f"fact_en: {fact_text}",
    ]
    if condition_text_uk:
        parts.append(f"condition_uk: {condition_text_uk}")
    if exception_text_uk:
        parts.append(f"exception_uk: {exception_text_uk}")
    if procedure_text_uk:
        parts.append(f"procedure_uk: {procedure_text_uk}")
    if thresholds_json:
        parts.append(f"thresholds: {thresholds_json}")
    if source_quote_uk:
        parts.append(f"quote_uk: {str(source_quote_uk)[:400]}")
    return "\n".join(parts)


def _provision_embedding_text(row: tuple) -> str:
    (provision_text,) = row
    return str(provision_text or "")


def _load_existing_ids(npz_path: Path) -> set[str]:
    """Load set of already-embedded IDs from a .npz file."""
    if not npz_path.exists():
        return set()
    try:
        data = np.load(str(npz_path), allow_pickle=True)
        return set(str(v) for v in data["ids"])
    except Exception:
        logger.debug("Failed to load existing embedding IDs from %s", npz_path)
        return set()


def _embed_table(
    *,
    db_path: Path,
    output_dir: Path,
    table: str,
    id_column: str,
    text_columns: str,
    text_builder: Callable[[tuple], str],
    npz_name: str,
    hnsw_name: str,
    model,
    batch_size: int,
    chunk_size: int,
    pause_seconds: float,
    incremental: bool = False,
) -> tuple[int, int]:
    """Embed a table and return (embedded_count, skipped_count)."""
    npz_path = output_dir / f"{npz_name}.npz"
    hnsw_path = output_dir / f"{hnsw_name}.hnsw"

    existing_ids: set[str] = set()
    existing_id_list: list[str] = []
    existing_vectors: np.ndarray | None = None

    if incremental:
        existing_ids = _load_existing_ids(npz_path)
        if existing_ids and npz_path.exists():
            data = np.load(str(npz_path), allow_pickle=True)
            existing_id_list = [str(v) for v in data["ids"]]
            existing_vectors = np.asarray(data["vectors"], dtype=np.float32)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        total = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        con.close()

    if total == 0:
        return 0, 0

    dim = model.get_sentence_embedding_dimension()

    all_ids: list[str] = list(existing_id_list) if existing_id_list else []
    chunks: list[np.ndarray] = []
    if existing_vectors is not None and existing_vectors.size > 0:
        chunks.append(existing_vectors)

    new_count = 0
    skipped = 0
    offset = 0

    while offset < total:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(
                f"SELECT {id_column}, {text_columns} FROM {table} "
                f"ORDER BY {id_column} LIMIT {chunk_size} OFFSET {offset}"
            ).fetchall()
        finally:
            con.close()

        if not rows:
            break

        # Filter out already-embedded IDs in incremental mode.
        if incremental and existing_ids:
            new_rows = [(r[0], r[1:]) for r in rows if str(r[0]) not in existing_ids]
            skipped += len(rows) - len(new_rows)
        else:
            new_rows = [(r[0], r[1:]) for r in rows]

        if new_rows:
            ids = [str(r[0]) for r in new_rows]
            texts = [text_builder(tuple(r[1]))[:32000] for r in new_rows]
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
            ).astype(np.float32)

            all_ids.extend(ids)
            chunks.append(vectors)
            new_count += len(ids)

        offset += len(rows)
        pause_between_batches(pause_seconds)

    if not all_ids:
        return 0, skipped

    full_vectors = np.vstack(chunks) if chunks else np.zeros((0, dim), dtype=np.float32)

    # Build HNSW from all vectors (existing + new).
    total_elements = len(all_ids)
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=total_elements, ef_construction=200, M=16)
    labels = np.arange(total_elements)
    index.add_items(full_vectors, labels)

    np.savez(str(npz_path), ids=np.array(all_ids, dtype=object), vectors=full_vectors)
    index.save_index(str(hnsw_path))
    return new_count, skipped


def build_local_embeddings_and_indexes(
    *,
    db_path: Path,
    output_dir: Path,
    embedding_model: str = "intfloat/multilingual-e5-large",
    embedding_device: str = "mps",
    embedding_batch_size: int = 24,
    embedding_chunk_size: int = 2000,
    thermal_pause_seconds: float = 0.0,
    incremental: bool = False,
    fp16: bool = False,
) -> EmbeddingStats:
    """Build local embeddings + HNSW for entities/facts/provisions."""
    from sentence_transformers import SentenceTransformer

    t0 = time.monotonic()

    model_kwargs = {}
    if fp16 and embedding_device in ("mps", "cuda"):
        try:
            import torch
            model_kwargs["torch_dtype"] = torch.float16
            logger.info("FP16 inference enabled for device=%s", embedding_device)
        except ImportError:
            pass

    if model_kwargs:
        model = SentenceTransformer(
            embedding_model,
            device=embedding_device,
            model_kwargs=model_kwargs,
        )
    else:
        model = SentenceTransformer(embedding_model, device=embedding_device)

    stats = EmbeddingStats()
    embedded, skipped = _embed_table(
        db_path=db_path,
        output_dir=output_dir,
        table="lex_entities",
        id_column="entity_id",
        text_columns="name_en, name_uk, entity_type, aliases_en, aliases_uk",
        text_builder=_entity_embedding_text,
        npz_name="lex_entity_embeddings",
        hnsw_name="lex_entity_index",
        model=model,
        batch_size=embedding_batch_size,
        chunk_size=embedding_chunk_size,
        pause_seconds=thermal_pause_seconds,
        incremental=incremental,
    )
    stats.entities_embedded = embedded
    stats.entities_skipped = skipped
    logger.info("Lex local embed: entities=%d (skipped=%d)", embedded, skipped)

    embedded, skipped = _embed_table(
        db_path=db_path,
        output_dir=output_dir,
        table="lex_facts",
        id_column="fact_id",
        text_columns=(
            "subject_en, subject_uk, predicate, object_en, object_uk, "
            "fact_text, norm_type, action_canon, norm_type_canon, "
            "condition_text_uk, exception_text_uk, procedure_text_uk, "
            "thresholds_json, source_quote_uk"
        ),
        text_builder=_fact_embedding_text,
        npz_name="lex_fact_embeddings",
        hnsw_name="lex_fact_index",
        model=model,
        batch_size=embedding_batch_size,
        chunk_size=embedding_chunk_size,
        pause_seconds=thermal_pause_seconds,
        incremental=incremental,
    )
    stats.facts_embedded = embedded
    stats.facts_skipped = skipped
    logger.info("Lex local embed: facts=%d (skipped=%d)", embedded, skipped)

    embedded, skipped = _embed_table(
        db_path=db_path,
        output_dir=output_dir,
        table="lex_provisions",
        id_column="provision_id",
        text_columns="provision_text",
        text_builder=_provision_embedding_text,
        npz_name="lex_provision_embeddings",
        hnsw_name="lex_provision_index",
        model=model,
        batch_size=embedding_batch_size,
        chunk_size=embedding_chunk_size,
        pause_seconds=thermal_pause_seconds,
        incremental=incremental,
    )
    stats.provisions_embedded = embedded
    stats.provisions_skipped = skipped
    logger.info("Lex local embed: provisions=%d (skipped=%d)", embedded, skipped)

    stats.elapsed_seconds = time.monotonic() - t0
    return stats


# Backward compatibility name (legacy code may call this symbol).
def build_embeddings_and_index(
    db_path: Path,
    output_dir: Path,
    *,
    backend=None,
    chunk_size: int = 2000,
) -> EmbeddingStats:
    return build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=output_dir,
        embedding_chunk_size=chunk_size,
    )
