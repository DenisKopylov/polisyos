"""OpenAI Batch API workflow for large-scale embeddings.

Workflow:
1) submit_embedding_batches(...)  -> creates batch jobs and writes manifest
2) collect_embedding_batches(...) -> downloads completed results and builds indexes
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

logger = logging.getLogger(__name__)

_MANIFEST_VERSION = 1
_DEFAULT_BATCH_INPUT_MAX_BYTES = 190 * 1024 * 1024  # keep margin under 200MB limit


@dataclass(frozen=True)
class _TableSpec:
    key: str
    table: str
    id_column: str
    text_columns: str
    npz_name: str
    hnsw_name: str


TABLE_SPECS: dict[str, _TableSpec] = {
    "entities": _TableSpec(
        key="entities",
        table="lex_entities",
        id_column="entity_id",
        text_columns="name_en, name_uk, entity_type, aliases_en, aliases_uk",
        npz_name="lex_entity_embeddings",
        hnsw_name="lex_entity_index",
    ),
    "facts": _TableSpec(
        key="facts",
        table="lex_facts",
        id_column="fact_id",
        text_columns=(
            "subject_en, subject_uk, predicate, object_en, object_uk, "
            "fact_text, norm_type, action_canon, norm_type_canon, "
            "condition_text_uk, exception_text_uk, procedure_text_uk, "
            "thresholds_json, source_quote_uk"
        ),
        npz_name="lex_fact_embeddings",
        hnsw_name="lex_fact_index",
    ),
    "provisions": _TableSpec(
        key="provisions",
        table="lex_provisions",
        id_column="provision_id",
        text_columns="provision_text",
        npz_name="lex_provision_embeddings",
        hnsw_name="lex_provision_index",
    ),
}


def _entity_embedding_text(row: tuple) -> str:
    name_en, name_uk, entity_type, aliases_en, aliases_uk = row
    parts = ["ENTITY", f"en: {name_en}", f"uk: {name_uk or ''}"]
    aliases: list[str] = []
    if aliases_en:
        aliases.extend(str(aliases_en).split("; ")[:5])
    if aliases_uk:
        aliases.extend(str(aliases_uk).split("; ")[:5])
    if aliases:
        parts.append(f"aliases: {'; '.join(aliases)}")
    parts.append(f"type: {entity_type}")
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
    return str(provision_text)


TEXT_BUILDERS = {
    "entities": _entity_embedding_text,
    "facts": _fact_embedding_text,
    "provisions": _provision_embedding_text,
}


class _TokenLimiter:
    """Token counter with tiktoken primary mode and char fallback."""

    def __init__(
        self,
        *,
        fallback_chars_per_token: int = 4,
        fallback_max_chars: int = 12_000,
    ) -> None:
        self._fallback_chars_per_token = max(1, fallback_chars_per_token)
        self._fallback_max_chars = max(1024, fallback_max_chars)
        self._encoder = None
        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding("cl100k_base")
            logger.info("tiktoken enabled for strict embedding token limits.")
        except Exception:
            logger.warning("tiktoken unavailable; using conservative character fallback.")

    def count(self, text: str) -> int:
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        return max(1, len(text) // self._fallback_chars_per_token)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        safe_max_tokens = max(1, max_tokens)
        if self._encoder is not None:
            encoded = self._encoder.encode(text)
            if len(encoded) <= safe_max_tokens:
                return text
            return self._encoder.decode(encoded[:safe_max_tokens])
        # Conservative fallback: keep chars well below 8192-token limit.
        return text[: min(len(text), self._fallback_max_chars)]


def _paths(output_dir: Path) -> dict[str, Path]:
    root = output_dir / "openai_batches"
    return {
        "root": root,
        "manifest": root / "manifest.json",
        "inputs": root / "inputs",
        "request_maps": root / "request_maps",
        "outputs": root / "outputs",
        "shards": root / "shards",
        "tmp": root / "tmp",
    }


def _ensure_dirs(output_dir: Path) -> dict[str, Path]:
    p = _paths(output_dir)
    for key in ("root", "inputs", "request_maps", "outputs", "shards", "tmp"):
        p[key].mkdir(parents=True, exist_ok=True)
    return p


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": _MANIFEST_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "batches": [],
            "builds": [],
        }
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid manifest format: {path}")
    return raw


def _save_manifest(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _iter_table_rows(
    *,
    db_path: Path,
    spec: _TableSpec,
    chunk_size: int,
) -> tuple[str, tuple]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        total = int(con.execute(f"SELECT COUNT(*) FROM {spec.table}").fetchone()[0])
    finally:
        con.close()

    offset = 0
    while offset < total:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(
                f"SELECT {spec.id_column}, {spec.text_columns} FROM {spec.table} "
                f"ORDER BY {spec.id_column} LIMIT {chunk_size} OFFSET {offset}"
            ).fetchall()
        finally:
            con.close()
        if not rows:
            break
        for row in rows:
            yield str(row[0]), row[1:]
        offset += len(rows)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (vectors / norms).astype(np.float32)


def submit_embedding_batches(
    *,
    db_path: Path,
    output_dir: Path,
    api_key: str,
    model: str = "text-embedding-3-large",
    dimensions: int = 3072,
    tables: tuple[str, ...] = ("entities", "facts", "provisions"),
    chunk_size: int = 5000,
    max_input_tokens: int = 8192,
    max_request_tokens: int = 250_000,
    max_inputs_per_request: int = 128,
    max_requests_per_batch: int = 50_000,
    max_inputs_per_batch: int = 50_000,
    max_batch_input_bytes: int = _DEFAULT_BATCH_INPUT_MAX_BYTES,
    fallback_max_chars: int = 12_000,
) -> dict[str, int]:
    """Create OpenAI embedding batches and persist manifest with batch IDs."""
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is required for embedding batch submission.")
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB database not found: {db_path}")

    from openai import OpenAI

    paths = _ensure_dirs(output_dir)
    manifest = _load_manifest(paths["manifest"])
    client = OpenAI(api_key=api_key)
    limiter = _TokenLimiter(fallback_max_chars=fallback_max_chars)
    run_id = datetime.now(UTC).strftime("run_%Y%m%dT%H%M%SZ")

    current_input_path: Path | None = None
    current_map_path: Path | None = None
    current_input_fh = None
    current_map_fh = None
    current_requests = 0
    current_inputs = 0
    current_bytes = 0
    batch_counter = 0
    request_counter = 0

    submitted_batches = 0
    submitted_requests = 0
    submitted_inputs = 0

    def _open_batch_files() -> None:
        nonlocal current_input_path, current_map_path
        nonlocal current_input_fh, current_map_fh
        nonlocal current_requests, current_inputs, current_bytes, batch_counter
        batch_counter += 1
        current_input_path = paths["inputs"] / f"{run_id}.batch_{batch_counter:04d}.jsonl"
        current_map_path = paths["request_maps"] / f"{run_id}.batch_{batch_counter:04d}.map.jsonl"
        current_input_fh = open(current_input_path, "w", encoding="utf-8")
        current_map_fh = open(current_map_path, "w", encoding="utf-8")
        current_requests = 0
        current_inputs = 0
        current_bytes = 0

    def _close_batch_files() -> None:
        nonlocal current_input_fh, current_map_fh
        if current_input_fh is not None:
            current_input_fh.close()
            current_input_fh = None
        if current_map_fh is not None:
            current_map_fh.close()
            current_map_fh = None

    def _submit_current_batch() -> None:
        nonlocal submitted_batches
        nonlocal current_input_path, current_map_path, current_requests, current_inputs
        if current_input_path is None or current_map_path is None:
            return
        if current_requests == 0:
            return

        with open(current_input_path, "rb") as batch_file:
            uploaded = client.files.create(file=batch_file, purpose="batch")
        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/embeddings",
            completion_window="24h",
            metadata={
                "pipeline": "polisyos.lex.batch",
                "run_id": run_id,
                "model": model,
                "dimensions": str(dimensions),
            },
        )
        manifest.setdefault("batches", []).append(
            {
                "run_id": run_id,
                "batch_id": batch.id,
                "status": str(getattr(batch, "status", "submitted")),
                "model": model,
                "dimensions": dimensions,
                "input_file_id": uploaded.id,
                "input_jsonl": str(current_input_path),
                "request_map_jsonl": str(current_map_path),
                "requests": current_requests,
                "inputs": current_inputs,
                "collected": False,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        submitted_batches += 1
        logger.info(
            "Submitted embedding batch %s with %d requests / %d inputs",
            batch.id,
            current_requests,
            current_inputs,
        )

    def _ensure_capacity_or_rollover(request_line_bytes: int, request_inputs: int) -> None:
        nonlocal current_requests, current_inputs, current_bytes
        if current_input_fh is None or current_map_fh is None:
            _open_batch_files()
            return

        will_overflow = (
            current_requests + 1 > max_requests_per_batch
            or current_inputs + request_inputs > max_inputs_per_batch
            or current_bytes + request_line_bytes > max_batch_input_bytes
        )
        if not will_overflow:
            return
        _close_batch_files()
        _submit_current_batch()
        _open_batch_files()

    for table in tables:
        if table not in TABLE_SPECS:
            raise ValueError(f"Unknown table for embeddings: {table}")
        spec = TABLE_SPECS[table]
        text_builder = TEXT_BUILDERS[table]
        pending_ids: list[str] = []
        pending_texts: list[str] = []
        pending_tokens = 0

        def _flush_request() -> None:
            nonlocal pending_ids, pending_texts, pending_tokens
            nonlocal request_counter, submitted_requests, submitted_inputs
            nonlocal current_requests, current_inputs, current_bytes
            if not pending_ids:
                return

            request_counter += 1
            custom_id = f"{run_id}:{table}:{request_counter}"
            request_payload = {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/embeddings",
                "body": {
                    "model": model,
                    "input": pending_texts,
                    "dimensions": dimensions,
                    "encoding_format": "float",
                },
            }
            request_line = json.dumps(request_payload, ensure_ascii=False)
            line_bytes = len(request_line.encode("utf-8")) + 1
            _ensure_capacity_or_rollover(line_bytes, len(pending_ids))

            assert current_input_fh is not None
            assert current_map_fh is not None
            current_input_fh.write(request_line + "\n")
            current_map_fh.write(
                json.dumps(
                    {
                        "custom_id": custom_id,
                        "table": table,
                        "ids": pending_ids,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            current_requests += 1
            current_inputs += len(pending_ids)
            current_bytes += line_bytes
            submitted_requests += 1
            submitted_inputs += len(pending_ids)

            pending_ids = []
            pending_texts = []
            pending_tokens = 0

        for row_id, row_values in _iter_table_rows(db_path=db_path, spec=spec, chunk_size=chunk_size):
            text = text_builder(row_values)
            text = limiter.truncate_to_tokens(text, max_tokens=max_input_tokens)
            token_count = limiter.count(text)
            if token_count <= 0:
                continue

            if pending_ids and (
                len(pending_ids) >= max_inputs_per_request
                or pending_tokens + token_count > max_request_tokens
            ):
                _flush_request()
            pending_ids.append(row_id)
            pending_texts.append(text)
            pending_tokens += token_count
        _flush_request()

    _close_batch_files()
    _submit_current_batch()
    _save_manifest(paths["manifest"], manifest)
    return {
        "batches_created": submitted_batches,
        "requests_submitted": submitted_requests,
        "inputs_submitted": submitted_inputs,
    }


class _ShardWriter:
    def __init__(self, *, shards_root: Path, table: str, shard_size: int = 5000) -> None:
        self._root = shards_root
        self._table = table
        self._shard_size = max(1, shard_size)
        self._ids: list[str] = []
        self._vectors: list[list[float]] = []
        self._counter = 0
        self._total = 0

    @property
    def total_rows(self) -> int:
        return self._total

    def add(self, ids: list[str], vectors: list[list[float]]) -> None:
        for row_id, vector in zip(ids, vectors, strict=True):
            self._ids.append(row_id)
            self._vectors.append(vector)
            if len(self._ids) >= self._shard_size:
                self.flush()

    def flush(self) -> None:
        if not self._ids:
            return
        self._counter += 1
        out_path = self._root / f"{self._table}.{self._counter:06d}.npz"
        vectors = np.array(self._vectors, dtype=np.float32)
        vectors = _l2_normalize(vectors)
        np.savez(
            out_path,
            ids=np.array(self._ids),
            vectors=vectors,
        )
        self._total += len(self._ids)
        self._ids = []
        self._vectors = []


def _load_request_map(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            custom_id = str(entry["custom_id"])
            out[custom_id] = {
                "table": str(entry["table"]),
                "ids": [str(v) for v in entry["ids"]],
            }
    return out


def _file_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    text_attr = getattr(content, "text", None)
    if isinstance(text_attr, str):
        return text_attr
    if callable(text_attr):
        maybe = text_attr()
        if isinstance(maybe, str):
            return maybe
    read_attr = getattr(content, "read", None)
    if callable(read_attr):
        raw = read_attr()
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        if isinstance(raw, str):
            return raw
    return str(content)


def collect_embedding_batches(
    *,
    output_dir: Path,
    api_key: str,
    wait_for_completion: bool = False,
    poll_interval_s: float = 20.0,
    build_index: bool = True,
) -> dict[str, int]:
    """Collect completed batches, write shards, and optionally build indexes."""
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is required for embedding batch collection.")

    from openai import OpenAI

    paths = _ensure_dirs(output_dir)
    manifest_path = paths["manifest"]
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Batch manifest not found: {manifest_path}. Run embed-batch submit first."
        )
    manifest = _load_manifest(manifest_path)
    batches = manifest.get("batches", [])
    if not isinstance(batches, list):
        raise ValueError("Invalid batch manifest format: 'batches' must be a list.")

    client = OpenAI(api_key=api_key)
    writers = {
        key: _ShardWriter(shards_root=paths["shards"], table=key)
        for key in TABLE_SPECS
    }
    completed_now = 0
    pending_now = 0
    failed_now = 0

    for entry in batches:
        if not isinstance(entry, dict):
            continue
        if entry.get("collected"):
            continue
        batch_id = str(entry.get("batch_id", "")).strip()
        if not batch_id:
            continue

        batch = client.batches.retrieve(batch_id)
        status = str(getattr(batch, "status", "") or "")
        if wait_for_completion:
            while status in {"validating", "in_progress", "finalizing"}:
                logger.info("Batch %s is %s, waiting %.1fs", batch_id, status, poll_interval_s)
                time.sleep(max(1.0, poll_interval_s))
                batch = client.batches.retrieve(batch_id)
                status = str(getattr(batch, "status", "") or "")

        entry["status"] = status
        if status != "completed":
            if status in {"failed", "cancelled", "expired"}:
                failed_now += 1
            else:
                pending_now += 1
            continue

        output_file_id = str(getattr(batch, "output_file_id", "") or "")
        if not output_file_id:
            failed_now += 1
            logger.warning("Batch %s completed without output_file_id", batch_id)
            continue

        request_map_path = Path(str(entry["request_map_jsonl"]))
        request_map = _load_request_map(request_map_path)
        output_content = client.files.content(output_file_id)
        output_text = _file_content_to_text(output_content)

        local_output_path = paths["outputs"] / f"{batch_id}.output.jsonl"
        with open(local_output_path, "w", encoding="utf-8") as fh:
            fh.write(output_text)

        for line in output_text.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            custom_id = str(item.get("custom_id", ""))
            mapping = request_map.get(custom_id)
            if mapping is None:
                continue
            if item.get("error"):
                logger.warning("Embedding request %s failed: %s", custom_id, item["error"])
                continue

            response = item.get("response") or {}
            status_code = int(response.get("status_code") or 0)
            if status_code != 200:
                logger.warning("Embedding request %s returned status=%d", custom_id, status_code)
                continue
            body = response.get("body") or {}
            data = body.get("data")
            if not isinstance(data, list):
                continue

            vectors = [d.get("embedding") for d in sorted(data, key=lambda d: int(d.get("index", 0)))]
            vectors = [v for v in vectors if isinstance(v, list)]
            ids = list(mapping["ids"])
            size = min(len(ids), len(vectors))
            if size <= 0:
                continue
            table = str(mapping["table"])
            writer = writers.get(table)
            if writer is None:
                continue
            writer.add(ids[:size], vectors[:size])

        entry["collected"] = True
        entry["collected_at"] = datetime.now(UTC).isoformat()
        entry["output_file_id"] = output_file_id
        entry["output_jsonl"] = str(local_output_path)
        completed_now += 1
        _save_manifest(manifest_path, manifest)

    for writer in writers.values():
        writer.flush()
    _save_manifest(manifest_path, manifest)

    built_indexes = 0
    if build_index:
        build_result = build_hnsw_from_shards(output_dir=output_dir)
        built_indexes = build_result["indexes_built"]
        manifest.setdefault("builds", []).append(
            {
                "type": "hnsw_from_shards",
                "at": datetime.now(UTC).isoformat(),
                "result": build_result,
            }
        )
        _save_manifest(manifest_path, manifest)

    return {
        "completed_batches": completed_now,
        "pending_batches": pending_now,
        "failed_batches": failed_now,
        "indexes_built": built_indexes,
    }


def build_hnsw_from_shards(
    *,
    output_dir: Path,
    ef_construction: int = 200,
    m: int = 16,
    ef_search: int = 100,
) -> dict[str, int]:
    """Build final *.npz + *.hnsw artifacts from shard files."""
    import hnswlib

    paths = _ensure_dirs(output_dir)
    indexes_built = 0
    vectors_built = 0

    for key, spec in TABLE_SPECS.items():
        shard_paths = sorted(paths["shards"].glob(f"{key}.*.npz"))
        if not shard_paths:
            continue

        total = 0
        dim = 0
        for shard_path in shard_paths:
            data = np.load(shard_path, allow_pickle=True)
            vectors = np.asarray(data["vectors"], dtype=np.float32)
            if vectors.ndim != 2:
                continue
            total += int(vectors.shape[0])
            dim = int(vectors.shape[1])
        if total == 0 or dim <= 0:
            continue

        tmp_vectors_path = paths["tmp"] / f"{key}.vectors.npy"
        mmap_vectors = np.lib.format.open_memmap(
            tmp_vectors_path,
            mode="w+",
            dtype=np.float32,
            shape=(total, dim),
        )
        ids: list[str] = []

        index = hnswlib.Index(space="cosine", dim=dim)
        index.init_index(max_elements=total, ef_construction=ef_construction, M=m)

        cursor = 0
        for shard_path in shard_paths:
            data = np.load(shard_path, allow_pickle=True)
            shard_ids = [str(v) for v in data["ids"]]
            shard_vectors = np.asarray(data["vectors"], dtype=np.float32)
            if shard_vectors.ndim != 2 or shard_vectors.size == 0:
                continue
            shard_vectors = _l2_normalize(shard_vectors)
            n = int(shard_vectors.shape[0])
            mmap_vectors[cursor : cursor + n] = shard_vectors
            ids.extend(shard_ids[:n])
            labels = np.arange(cursor, cursor + n)
            index.add_items(shard_vectors, labels)
            cursor += n

        if cursor == 0:
            continue

        index.set_ef(ef_search)
        out_hnsw = output_dir / f"{spec.hnsw_name}.hnsw"
        out_npz = output_dir / f"{spec.npz_name}.npz"
        index.save_index(str(out_hnsw))
        np.savez(out_npz, ids=np.array(ids), vectors=mmap_vectors[:cursor])
        vectors_built += cursor
        indexes_built += 1

        try:
            tmp_vectors_path.unlink()
        except FileNotFoundError:
            pass

    return {
        "indexes_built": indexes_built,
        "vectors_built": vectors_built,
    }
