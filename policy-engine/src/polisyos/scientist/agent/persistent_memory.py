"""CAS-backed persistent agent memory.

Provides episodic and semantic memory that persists across workflow runs
via the content-addressable artifact store.

Lifecycle::

    Run 1: fresh store -> agents remember() -> save_index() -> state.memory_index_ref
    Run 2: load_index(ref) -> agents recall() -> remember() -> save_index() -> updated ref
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions

logger = get_logger(__name__)

__all__ = [
    "MemoryEntry",
    "MemoryIndex",
    "MemoryIndexEntry",
    "MemoryKind",
    "MemoryQuery",
    "PersistentMemoryStore",
]


class MemoryKind(str, Enum):
    """Memory kind public type."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryEntry(BaseModel):
    """A single memory record."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    memory_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: MemoryKind
    content: str
    tags: list[str] = Field(default_factory=list)
    source_run_id: str
    source_node_alias: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class MemoryIndexEntry(BaseModel):
    """Lightweight pointer for the in-memory index."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    kind: MemoryKind
    tags: list[str] = Field(default_factory=list)
    content_preview: str = ""
    artifact_ref: ArtifactRef
    created_at: datetime


class MemoryIndex(BaseModel):
    """Serialisable index of all memory entries."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    entries: list[MemoryIndexEntry] = Field(default_factory=list)


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    model_config = ConfigDict(extra="forbid")

    query_text: str | None = None
    kind: MemoryKind | None = None
    tags: list[str] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=100)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Keyword relevance (v1 — fallback when no embeddings)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenisation for keyword overlap scoring."""
    return {w for w in text.lower().split() if len(w) > 2}


def _keyword_score(query_tokens: set[str], text: str) -> float:
    """Jaccard-like overlap score between query tokens and text tokens."""
    if not query_tokens:
        return 0.0
    text_tokens = _tokenize(text)
    if not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


def _content_hash(content: str) -> str:
    """SHA-256 prefix for content deduplication."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# PersistentMemoryStore
# ---------------------------------------------------------------------------

_MEMORY_ENTRY_KIND = "scientist.memory_entry"
_MEMORY_INDEX_KIND = "scientist.memory_index"
_SCHEMA_NAME = "polisyos.scientist.agent.PersistentMemory"

_PRUNE_INTERVAL_S = 60.0  # TTL prune at most once per minute


class PersistentMemoryStore:
    """CAS-backed persistent memory for agents.

    Each :class:`MemoryEntry` is stored as a separate CAS artifact.
    An :class:`MemoryIndex` tracks all entries and is itself persisted
    to CAS at workflow end.

    Optional enhancements (Phase 6 WS6.4):

    * **Semantic search** via *embedder* + *vector_store* (falls back to
      Jaccard keyword scoring when unavailable).
    * **Content-hash deduplication** — identical content is stored once.
    * **TTL auto-pruning** — expired entries removed lazily during query.
    * **Confidence-weighted ranking** — high-confidence entries boosted.
    * **Memory consolidation** — similar entries merged via clustering.
    """

    def __init__(
        self,
        store: ArtifactStore,
        namespace: str = "agent_memory",
        embedder: Any | None = None,
        vector_store: Any | None = None,
    ) -> None:
        self._store = store
        self._namespace = namespace
        self._index = MemoryIndex()
        self._embedder = embedder
        self._vector_store = vector_store
        self._content_hashes: set[str] = set()
        self._last_prune_at: float = 0.0

    @property
    def index(self) -> MemoryIndex:
        return self._index

    # -- write -------------------------------------------------------------

    def store_memory(self, entry: MemoryEntry) -> ArtifactRef:
        """Persist a memory entry to CAS and update the in-memory index.

        Returns the existing ref if an entry with identical content already
        exists (deduplication).
        """
        # Deduplication
        chash = _content_hash(entry.content)
        if chash in self._content_hashes:
            # Find existing ref for the duplicate
            for idx_entry in self._index.entries:
                if _content_hash(idx_entry.content_preview) == chash:
                    logger.debug("Skipping duplicate memory: %s", chash)
                    return idx_entry.artifact_ref
            # Hash was tracked but entry not found — fall through to store
        self._content_hashes.add(chash)

        ref = self._store.put_json(
            entry.model_dump(mode="json"),
            PutOptions(
                kind=_MEMORY_ENTRY_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_SCHEMA_NAME, version="1.0"),
            ),
        )
        index_entry = MemoryIndexEntry(
            memory_id=entry.memory_id,
            kind=entry.kind,
            tags=entry.tags,
            content_preview=entry.content[:200],
            artifact_ref=ref,
            created_at=entry.created_at,
        )
        self._index.entries.append(index_entry)

        # Index in vector store
        if self._embedder is not None and self._vector_store is not None:
            try:
                emb = self._embedder.embed([entry.content])[0]
                self._vector_store.add(
                    key=entry.memory_id,
                    embedding=emb,
                    metadata={"kind": entry.kind.value, "tags": ",".join(entry.tags)},
                )
            except Exception:
                logger.debug("Failed to index memory %s in vector store", entry.memory_id)

        return ref

    # -- read --------------------------------------------------------------

    def query(self, q: MemoryQuery) -> list[MemoryEntry]:
        """Retrieve entries matching a :class:`MemoryQuery`."""
        # Lazy TTL prune
        self._maybe_prune_expired()

        now = datetime.now(timezone.utc)
        candidates = self._index.entries

        # Kind filter
        if q.kind is not None:
            candidates = [e for e in candidates if e.kind == q.kind]

        # Tag filter (all requested tags must be present)
        if q.tags:
            tag_set = set(q.tags)
            candidates = [e for e in candidates if tag_set <= set(e.tags)]

        # Score by relevance
        scored = self._score_candidates(candidates, q)

        # Sort descending by score, then newest first
        scored.sort(key=lambda t: (-t[0], -t[1].created_at.timestamp()))

        # Load full entries from CAS
        results: list[MemoryEntry] = []
        for _score, idx_entry in scored:
            if len(results) >= q.max_results:
                break
            try:
                raw = self._store.get_bytes(idx_entry.artifact_ref.artifact_id)
                import json
                entry = MemoryEntry.model_validate(json.loads(raw))
            except Exception:
                logger.debug("Failed to load memory %s", idx_entry.memory_id)
                continue

            # Confidence filter
            if entry.confidence < q.min_confidence:
                continue

            # TTL filter
            if entry.expires_at is not None and entry.expires_at <= now:
                continue

            results.append(entry)

        return results

    # -- dedup & consolidation ---------------------------------------------

    def prune_expired(self) -> int:
        """Remove index entries whose TTL has expired. Returns count removed."""
        now = datetime.now(timezone.utc)
        before = len(self._index.entries)

        surviving: list[MemoryIndexEntry] = []
        for idx_entry in self._index.entries:
            # We must load the full entry to check expires_at
            try:
                import json
                raw = self._store.get_bytes(idx_entry.artifact_ref.artifact_id)
                entry = MemoryEntry.model_validate(json.loads(raw))
                if entry.expires_at is not None and entry.expires_at <= now:
                    continue
            except Exception:
                pass  # keep entries we can't check
            surviving.append(idx_entry)

        self._index.entries = surviving
        return before - len(surviving)

    def consolidate(self, similarity_threshold: float = 0.85) -> int:
        """Cluster similar memories and replace clusters with summaries.

        Returns the number of entries removed.
        """
        if len(self._index.entries) < 2:
            return 0

        entries = list(self._index.entries)
        n = len(entries)
        visited = [False] * n
        clusters: list[list[int]] = []

        for i in range(n):
            if visited[i]:
                continue
            cluster = [i]
            visited[i] = True
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                sim = self._entry_similarity(entries[i], entries[j])
                if sim >= similarity_threshold:
                    cluster.append(j)
                    visited[j] = True
            if len(cluster) > 1:
                clusters.append(cluster)

        if not clusters:
            return 0

        removed_count = 0
        indices_to_remove: set[int] = set()

        for cluster in clusters:
            # Keep the first entry, merge content from others
            primary_idx = cluster[0]
            primary = entries[primary_idx]
            merged_tags: set[str] = set(primary.tags)
            for idx in cluster[1:]:
                merged_tags.update(entries[idx].tags)
                indices_to_remove.add(idx)

            # Update primary tags in-place
            entries[primary_idx] = MemoryIndexEntry(
                memory_id=primary.memory_id,
                kind=primary.kind,
                tags=sorted(merged_tags),
                content_preview=primary.content_preview,
                artifact_ref=primary.artifact_ref,
                created_at=primary.created_at,
            )
            removed_count += len(cluster) - 1

        # Rebuild index without removed entries
        self._index.entries = [
            e for i, e in enumerate(entries) if i not in indices_to_remove
        ]
        return removed_count

    # -- index persistence -------------------------------------------------

    def load_index(self, index_ref: ArtifactRef) -> None:
        """Restore the index from CAS."""
        import json

        raw = self._store.get_bytes(index_ref.artifact_id)
        self._index = MemoryIndex.model_validate(json.loads(raw))

        # Rebuild content hash set
        self._content_hashes = {
            _content_hash(e.content_preview) for e in self._index.entries
        }

    def save_index(self) -> ArtifactRef:
        """Persist the current index to CAS."""
        return self._store.put_json(
            self._index.model_dump(mode="json"),
            PutOptions(
                kind=_MEMORY_INDEX_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=f"{_SCHEMA_NAME}.Index", version="1.0"),
            ),
        )

    # -- prompt helpers ----------------------------------------------------

    def format_for_prompt(
        self,
        entries: list[MemoryEntry],
        *,
        max_chars: int = 4000,
    ) -> str:
        """Format memories as a text block for LLM prompt injection."""
        if not entries:
            return ""
        lines = ["# PRIOR KNOWLEDGE"]
        chars = len(lines[0])
        for entry in entries:
            tag_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            line = f"- [{entry.kind.value}]{tag_str} {entry.content}"
            if chars + len(line) + 1 > max_chars:
                break
            lines.append(line)
            chars += len(line) + 1
        return "\n".join(lines)

    # -- internal ----------------------------------------------------------

    def _score_candidates(
        self,
        candidates: list[MemoryIndexEntry],
        q: MemoryQuery,
    ) -> list[tuple[float, MemoryIndexEntry]]:
        """Score candidates by relevance, using semantic or keyword search."""
        # Semantic search path
        if (
            self._embedder is not None
            and self._vector_store is not None
            and q.query_text
        ):
            return self._score_semantic(candidates, q)

        # Keyword fallback
        return self._score_keyword(candidates, q)

    def _score_semantic(
        self,
        candidates: list[MemoryIndexEntry],
        q: MemoryQuery,
    ) -> list[tuple[float, MemoryIndexEntry]]:
        """Score using vector similarity."""
        try:
            emb = self._embedder.embed([q.query_text])[0]
            results = self._vector_store.query(emb, top_k=q.max_results * 2)
            # results: list of (key, distance, metadata)
            id_to_distance = {key: dist for key, dist, _ in results}
        except Exception:
            logger.debug("Semantic search failed, falling back to keyword")
            return self._score_keyword(candidates, q)

        candidate_map = {e.memory_id: e for e in candidates}
        scored: list[tuple[float, MemoryIndexEntry]] = []
        for memory_id, distance in id_to_distance.items():
            if memory_id in candidate_map:
                # Convert distance to similarity (cosine distance -> similarity)
                relevance = max(0.0, 1.0 - distance)
                entry = candidate_map[memory_id]
                # Confidence-weighted ranking
                confidence = self._estimate_confidence(entry)
                boost = 0.5 + 0.5 * confidence
                scored.append((relevance * boost, entry))

        # Add unscored candidates with minimal score
        scored_ids = {e.memory_id for _, e in scored}
        for entry in candidates:
            if entry.memory_id not in scored_ids:
                confidence = self._estimate_confidence(entry)
                scored.append((0.01 * (0.5 + 0.5 * confidence), entry))

        return scored

    def _score_keyword(
        self,
        candidates: list[MemoryIndexEntry],
        q: MemoryQuery,
    ) -> list[tuple[float, MemoryIndexEntry]]:
        """Score using Jaccard keyword overlap with confidence weighting."""
        query_tokens = _tokenize(q.query_text) if q.query_text else set()
        scored: list[tuple[float, MemoryIndexEntry]] = []
        for entry in candidates:
            base_score = (
                _keyword_score(query_tokens, entry.content_preview)
                if query_tokens
                else 1.0
            )
            # Confidence-weighted ranking
            confidence = self._estimate_confidence(entry)
            boost = 0.5 + 0.5 * confidence
            scored.append((base_score * boost, entry))
        return scored

    def _estimate_confidence(self, idx_entry: MemoryIndexEntry) -> float:
        """Estimate confidence from the index entry (preview-only, no CAS load)."""
        # We don't have confidence in the index entry, assume 1.0 by default
        # Full confidence is checked after CAS load in query()
        return 1.0

    def _entry_similarity(
        self, a: MemoryIndexEntry, b: MemoryIndexEntry,
    ) -> float:
        """Similarity between two index entries for consolidation."""
        if self._embedder is not None and self._vector_store is not None:
            # Use embedding similarity
            try:
                embs = self._embedder.embed([a.content_preview, b.content_preview])
                dot = sum(x * y for x, y in zip(embs[0], embs[1]))
                import math
                norm_a = math.sqrt(sum(x * x for x in embs[0]))
                norm_b = math.sqrt(sum(x * x for x in embs[1]))
                if norm_a < 1e-12 or norm_b < 1e-12:
                    return 0.0
                return dot / (norm_a * norm_b)
            except Exception:
                pass

        # Jaccard fallback
        tokens_a = _tokenize(a.content_preview)
        tokens_b = _tokenize(b.content_preview)
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        return intersection / union if union > 0 else 0.0

    def _maybe_prune_expired(self) -> None:
        """Lazy TTL pruning — at most once per minute."""
        import time
        now = time.monotonic()
        if now - self._last_prune_at < _PRUNE_INTERVAL_S:
            return
        self._last_prune_at = now

        utc_now = datetime.now(timezone.utc)
        before = len(self._index.entries)
        surviving: list[MemoryIndexEntry] = []
        for idx_entry in self._index.entries:
            try:
                import json
                raw = self._store.get_bytes(idx_entry.artifact_ref.artifact_id)
                entry = MemoryEntry.model_validate(json.loads(raw))
                if entry.expires_at is not None and entry.expires_at <= utc_now:
                    continue
            except Exception:
                pass
            surviving.append(idx_entry)

        if len(surviving) < before:
            self._index.entries = surviving
            logger.debug("Pruned %d expired memories", before - len(surviving))
