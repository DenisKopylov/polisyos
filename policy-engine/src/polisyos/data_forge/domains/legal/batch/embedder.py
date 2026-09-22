"""Local sentence-transformers embeddings for Lex graph tables."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import duckdb
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.data_forge.kernel.embeddings import (
    _build_embedding_generation_from_vectors,
    _generator_rule_version,
    resolve_embedding_generation,
)
from polisyos.data_forge.kernel.io.generation_basis import build_generation_basis
from polisyos.data_forge.kernel.runtime import pause_between_batches

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = get_logger(__name__)

LEGAL_EMBEDDING_PROJECTION_RULE_VERSION = "policyos.legal.embedding.v1"
_LEGAL_GENERATION_ROOT = ".legal_embedding_generations"


@dataclass
class EmbeddingStats:
    """Embedding stats public type."""

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


def _generation_index_dir(output_dir: Path, npz_name: str) -> Path:
    """Return the authoritative generation directory for one legal projection."""
    return output_dir / _LEGAL_GENERATION_ROOT / npz_name


def _load_reusable_vectors(
    *,
    index_dir: Path,
    legacy_embeddings_path: Path,
    legacy_index_path: Path,
    current_basis,
    embedding_model: str,
    embedding_device: str,
    embedding_dimension: int,
    basis_kind: str,
    projection_rule_version: str,
    incremental: bool,
) -> dict[str, np.ndarray]:
    """Load only vectors proven reusable by the selected generation metadata."""
    if not incremental:
        return {}

    reference = resolve_embedding_generation(
        index_dir,
        legacy_embeddings_path=legacy_embeddings_path,
        legacy_index_path=legacy_index_path,
    )
    # A legacy flat pair has no content-bound basis and is deliberately not a
    # cache.  The selected generation is the only source eligible for reuse.
    if reference is None or not reference.selected or reference.status != "complete":
        return {}

    inventory = reference.inventory
    if (
        inventory.get("embedding_model") != embedding_model
        or inventory.get("embedding_device") != embedding_device
    ):
        return {}
    try:
        if int(inventory["embedding_dimension"]) != int(embedding_dimension):
            return {}
    except (KeyError, TypeError, ValueError):
        return {}

    expected_rule_version = _generator_rule_version(
        projection_rule_version=projection_rule_version,
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        embedding_dimension=embedding_dimension,
    )
    persisted_basis = inventory.get("basis")
    if not isinstance(persisted_basis, dict):
        return {}
    if (
        persisted_basis.get("basis_kind") != basis_kind
        or persisted_basis.get("generator_rule_version") != expected_rule_version
    ):
        return {}

    old_identities: dict[str, str] = {}
    raw_members = persisted_basis.get("members")
    if not isinstance(raw_members, list):
        return {}
    for raw_member in raw_members:
        if not isinstance(raw_member, dict):
            return {}
        identifier = raw_member.get("identifier")
        content_identity = raw_member.get("content_identity")
        if not isinstance(identifier, str) or not isinstance(content_identity, str):
            return {}
        old_identities[identifier] = content_identity

    current_identities = {
        member.identifier: member.content_identity for member in current_basis.members
    }
    if not current_identities:
        return {}

    try:
        with np.load(str(reference.embeddings_path), allow_pickle=True) as payload:
            old_ids = tuple(str(value) for value in payload["ids"].tolist())
            old_vectors = np.asarray(payload["vectors"], dtype=np.float32)
    except (KeyError, OSError, TypeError, ValueError):
        return {}

    if (
        old_ids != reference.ids
        or old_vectors.ndim != 2
        or old_vectors.shape != (len(old_ids), int(embedding_dimension))
        or not np.isfinite(old_vectors).all()
    ):
        return {}
    old_vectors_by_id = {
        identifier: old_vectors[index] for index, identifier in enumerate(old_ids)
    }
    return {
        identifier: old_vectors_by_id[identifier]
        for identifier, content_identity in current_identities.items()
        if old_identities.get(identifier) == content_identity
        and identifier in old_vectors_by_id
    }


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
    embedding_model: str,
    embedding_device: str,
    batch_size: int,
    chunk_size: int,
    pause_seconds: float,
    incremental: bool = False,
) -> tuple[int, int]:
    """Embed a table and return (embedded_count, skipped_count)."""
    npz_path = output_dir / f"{npz_name}.npz"
    hnsw_path = output_dir / f"{hnsw_name}.hnsw"

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        total = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        con.close()

    dim = int(model.get_sentence_embedding_dimension())
    if dim < 1:
        raise ValueError("embedding model dimension must be positive")

    current_rows: list[tuple[str, str]] = []
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
        current_rows.extend(
            (str(row[0]), text_builder(tuple(row[1:]))[:32000]) for row in rows
        )
        offset += len(rows)

    current_rows.sort(key=lambda row: row[0])
    if len({identifier for identifier, _ in current_rows}) != len(current_rows):
        raise ValueError(f"{table} contains duplicate {id_column} values")

    basis_kind = f"legal_{table}_embedding"
    projection_rule_version = LEGAL_EMBEDDING_PROJECTION_RULE_VERSION
    current_basis = None
    if current_rows:
        current_basis = build_generation_basis(
            basis_kind=basis_kind,
            generator_rule_version=_generator_rule_version(
                projection_rule_version=projection_rule_version,
                embedding_model=embedding_model,
                embedding_device=embedding_device,
                embedding_dimension=dim,
            ),
            members=[
                (identifier, text.encode("utf-8")) for identifier, text in current_rows
            ],
        )

    reusable_vectors = (
        _load_reusable_vectors(
            index_dir=_generation_index_dir(output_dir, npz_name),
            legacy_embeddings_path=npz_path,
            legacy_index_path=hnsw_path,
            current_basis=current_basis,
            embedding_model=embedding_model,
            embedding_device=embedding_device,
            embedding_dimension=dim,
            basis_kind=basis_kind,
            projection_rule_version=projection_rule_version,
            incremental=incremental,
        )
        if current_basis is not None
        else {}
    )

    rows_to_encode = [
        row for row in current_rows if row[0] not in reusable_vectors
    ]
    encoded_vectors: dict[str, np.ndarray] = {}
    for start in range(0, len(rows_to_encode), chunk_size):
        batch_rows = rows_to_encode[start : start + chunk_size]
        texts = [text for _identifier, text in batch_rows]
        raw_vectors = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        vectors = np.asarray(raw_vectors, dtype=np.float32)
        if (
            vectors.ndim != 2
            or vectors.shape != (len(batch_rows), dim)
            or not np.isfinite(vectors).all()
        ):
            raise ValueError("embedding model returned invalid vector shape or values")
        encoded_vectors.update(
            (identifier, vectors[index])
            for index, (identifier, _text) in enumerate(batch_rows)
        )
        pause_between_batches(pause_seconds)

    ordered_vectors = [
        reusable_vectors[identifier]
        if identifier in reusable_vectors
        else encoded_vectors[identifier]
        for identifier, _text in current_rows
    ]
    full_vectors = (
        np.vstack(ordered_vectors)
        if ordered_vectors
        else np.empty((0, dim), dtype=np.float32)
    )
    _build_embedding_generation_from_vectors(
        rows=current_rows,
        vectors=full_vectors,
        index_dir=_generation_index_dir(output_dir, npz_name),
        embedding_model=embedding_model,
        embedding_device=embedding_device,
        embedding_dimension=dim,
        basis_kind=basis_kind,
        projection_rule_version=projection_rule_version,
        legacy_embeddings_path=npz_path,
        legacy_index_path=hnsw_path,
    )
    new_count = len(rows_to_encode)
    skipped = len(reusable_vectors)
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
        embedding_model=embedding_model,
        embedding_device=embedding_device,
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
        embedding_model=embedding_model,
        embedding_device=embedding_device,
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
        embedding_model=embedding_model,
        embedding_device=embedding_device,
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
    """Build embeddings and index."""
    if backend is not None:
        raise ValueError("unsupported backend: local legal embeddings are canonical")
    return build_local_embeddings_and_indexes(
        db_path=db_path,
        output_dir=output_dir,
        embedding_model="intfloat/multilingual-e5-large",
        embedding_device="mps",
        embedding_chunk_size=chunk_size,
    )
