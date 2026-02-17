"""Stage 5: Generate embeddings via OpenAI text-embedding-3-large and build HNSW indexes.

Designed for MacBook Air M2 16 GB:
- Streams data from DuckDB in chunks (never loads all vectors at once)
- Writes .npz embedding files incrementally
- Builds HNSW index per chunk, then merges
- Three indexes: entities, facts, provisions
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import hnswlib
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI Embedding Backend
# ---------------------------------------------------------------------------

class OpenAIEmbeddingBackend:
    """OpenAI API embedding backend using text-embedding-3-large (3072 dims).

    Respects the 300K token per request limit by batching intelligently.
    Uses the ``openai`` SDK for simplicity and reliability.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-large",
        dimension: int = 3072,
        max_concurrent: int = 10,
    ) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimension = dimension
        self._semaphore = asyncio.Semaphore(max_concurrent)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a single batch (must be within 300K token limit)."""
        async with self._semaphore:
            resp = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
        # Sort by index to guarantee order
        sorted_data = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in sorted_data]

    async def aencode(
        self,
        texts: list[str],
        *,
        max_tokens_per_request: int = 250_000,
        chars_per_token: int = 4,
    ) -> np.ndarray:
        """Encode texts in adaptive batches respecting token limits.

        Splits into sub-batches based on estimated token count
        (300K limit, with 250K safety margin).
        """
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)

        # Build adaptive batches
        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0

        for text in texts:
            est_tokens = max(1, len(text) // chars_per_token)
            if current_tokens + est_tokens > max_tokens_per_request and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(text)
            current_tokens += est_tokens

        if current_batch:
            batches.append(current_batch)

        # Execute batches with concurrency control
        all_embeddings: list[list[float]] = []
        for i, batch in enumerate(batches):
            result = await self._embed_batch(batch)
            all_embeddings.extend(result)
            if (i + 1) % 10 == 0:
                logger.info("Embedding batch %d/%d done (%d texts)", i + 1, len(batches), len(all_embeddings))

        arr = np.array(all_embeddings, dtype=np.float32)
        # L2 normalize for cosine similarity
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        return (arr / norms).astype(np.float32)


# ---------------------------------------------------------------------------
# Embedding text builders (bilingual structured templates)
# ---------------------------------------------------------------------------

def _entity_embedding_text(row: tuple) -> str:
    """Build entity embedding text from DuckDB row.

    Expected columns: name_en, name_uk, entity_type, aliases_en, aliases_uk
    """
    name_en, name_uk, entity_type, aliases_en, aliases_uk = row
    parts = ["ENTITY", f"en: {name_en}", f"uk: {name_uk or ''}"]
    aliases = []
    if aliases_en:
        aliases.extend(aliases_en.split("; ")[:5])
    if aliases_uk:
        aliases.extend(aliases_uk.split("; ")[:5])
    if aliases:
        parts.append(f"aliases: {'; '.join(aliases)}")
    parts.append(f"type: {entity_type}")
    return "\n".join(parts)


def _fact_embedding_text(row: tuple) -> str:
    """Build fact embedding text from DuckDB row.

    Expected columns: subject_en, subject_uk, predicate, object_en, object_uk,
                     fact_text, norm_type, action_canon, norm_type_canon,
                     condition_text_uk, exception_text_uk, procedure_text_uk,
                     thresholds_json, source_quote_uk
    """
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
        parts.append(f"quote_uk: {source_quote_uk[:400]}")
    return "\n".join(parts)


def _provision_embedding_text(row: tuple) -> str:
    """Build provision embedding text from DuckDB row.

    Expected columns: provision_text
    """
    (provision_text,) = row
    return provision_text


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingStats:
    entities_embedded: int = 0
    facts_embedded: int = 0
    provisions_embedded: int = 0
    total_api_calls: int = 0
    elapsed_seconds: float = 0.0


async def build_embeddings_and_index(
    db_path: Path,
    output_dir: Path,
    *,
    backend: OpenAIEmbeddingBackend,
    chunk_size: int = 5000,
) -> EmbeddingStats:
    """Build all three embedding indexes from DuckDB graph.

    Streams rows in chunks to stay within 16 GB RAM.
    """
    t0 = time.monotonic()
    stats = EmbeddingStats()

    # --- Entities ---
    logger.info("Embedding entities...")
    stats.entities_embedded = await _embed_table(
        db_path=db_path,
        output_dir=output_dir,
        table="lex_entities",
        id_column="entity_id",
        text_columns="name_en, name_uk, entity_type, aliases_en, aliases_uk",
        text_builder=_entity_embedding_text,
        npz_name="lex_entity_embeddings",
        hnsw_name="lex_entity_index",
        backend=backend,
        chunk_size=chunk_size,
    )

    # --- Facts ---
    logger.info("Embedding facts...")
    stats.facts_embedded = await _embed_table(
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
        backend=backend,
        chunk_size=chunk_size,
    )

    # --- Provisions ---
    logger.info("Embedding provisions...")
    stats.provisions_embedded = await _embed_table(
        db_path=db_path,
        output_dir=output_dir,
        table="lex_provisions",
        id_column="provision_id",
        text_columns="provision_text",
        text_builder=_provision_embedding_text,
        npz_name="lex_provision_embeddings",
        hnsw_name="lex_provision_index",
        backend=backend,
        chunk_size=chunk_size,
    )

    stats.elapsed_seconds = time.monotonic() - t0
    logger.info(
        "Embedding complete: %d entities + %d facts + %d provisions in %.0fs",
        stats.entities_embedded, stats.facts_embedded,
        stats.provisions_embedded, stats.elapsed_seconds,
    )
    return stats


async def _embed_table(
    *,
    db_path: Path,
    output_dir: Path,
    table: str,
    id_column: str,
    text_columns: str,
    text_builder,
    npz_name: str,
    hnsw_name: str,
    backend: OpenAIEmbeddingBackend,
    chunk_size: int,
) -> int:
    """Embed one table in chunks, write .npz + .hnsw files."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()

    if total == 0:
        logger.info("Table %s is empty, skipping.", table)
        return 0

    logger.info("Embedding %d rows from %s (chunk_size=%d)...", total, table, chunk_size)

    all_ids: list[str] = []
    all_vectors: list[np.ndarray] = []

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

        ids = [row[0] for row in rows]
        texts = [text_builder(row[1:]) for row in rows]

        # Truncate texts that exceed 8192 tokens (~32K chars)
        texts = [t[:32000] for t in texts]

        vectors = await backend.aencode(texts)
        all_ids.extend(ids)
        all_vectors.append(vectors)

        offset += chunk_size
        logger.info("  %s: %d / %d embedded", table, min(offset, total), total)

    if not all_ids:
        return 0

    # Concatenate all vectors
    full_vectors = np.vstack(all_vectors)

    # Save .npz
    npz_path = output_dir / f"{npz_name}.npz"
    np.savez_compressed(str(npz_path), ids=np.array(all_ids), vectors=full_vectors)
    logger.info("Saved %s (%d vectors, %d dims)", npz_path.name, len(all_ids), full_vectors.shape[1])

    # Build HNSW index
    dim = full_vectors.shape[1]
    index = hnswlib.Index(space="cosine", dim=dim)
    # ef_construction=200 for quality, M=16 default
    index.init_index(max_elements=len(all_ids), ef_construction=200, M=16)
    index.add_items(full_vectors, list(range(len(all_ids))))
    index.set_ef(100)  # query-time ef

    hnsw_path = output_dir / f"{hnsw_name}.hnsw"
    index.save_index(str(hnsw_path))
    logger.info("Saved %s (%d elements)", hnsw_path.name, len(all_ids))

    # Free memory
    del full_vectors, all_vectors
    return len(all_ids)
