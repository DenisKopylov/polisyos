"""CAS-backed persistent agent memory.

Provides episodic and semantic memory that persists across workflow runs
via the content-addressable artifact store.

Lifecycle::

    Run 1: fresh store → agents remember() → save_index() → state.memory_index_ref
    Run 2: load_index(ref) → agents recall() → remember() → save_index() → updated ref
"""

from __future__ import annotations

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
# Keyword relevance (v1 — no embeddings)
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


# ---------------------------------------------------------------------------
# PersistentMemoryStore
# ---------------------------------------------------------------------------

_MEMORY_ENTRY_KIND = "scientist.memory_entry"
_MEMORY_INDEX_KIND = "scientist.memory_index"
_SCHEMA_NAME = "polisyos.scientist.agent.PersistentMemory"


class PersistentMemoryStore:
    """CAS-backed persistent memory for agents.

    Each :class:`MemoryEntry` is stored as a separate CAS artifact.
    An :class:`MemoryIndex` tracks all entries and is itself persisted
    to CAS at workflow end.
    """

    def __init__(
        self,
        store: ArtifactStore,
        namespace: str = "agent_memory",
    ) -> None:
        self._store = store
        self._namespace = namespace
        self._index = MemoryIndex()

    @property
    def index(self) -> MemoryIndex:
        return self._index

    # -- write -------------------------------------------------------------

    def store_memory(self, entry: MemoryEntry) -> ArtifactRef:
        """Persist a memory entry to CAS and update the in-memory index."""
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
        return ref

    # -- read --------------------------------------------------------------

    def query(self, q: MemoryQuery) -> list[MemoryEntry]:
        """Retrieve entries matching a :class:`MemoryQuery`."""
        now = datetime.now(timezone.utc)
        candidates = self._index.entries

        # Kind filter
        if q.kind is not None:
            candidates = [e for e in candidates if e.kind == q.kind]

        # Tag filter (all requested tags must be present)
        if q.tags:
            tag_set = set(q.tags)
            candidates = [e for e in candidates if tag_set <= set(e.tags)]

        # Score by keyword relevance
        query_tokens = _tokenize(q.query_text) if q.query_text else set()
        scored: list[tuple[float, MemoryIndexEntry]] = []
        for entry in candidates:
            score = _keyword_score(query_tokens, entry.content_preview) if query_tokens else 1.0
            scored.append((score, entry))

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

    # -- index persistence -------------------------------------------------

    def load_index(self, index_ref: ArtifactRef) -> None:
        """Restore the index from CAS."""
        import json

        raw = self._store.get_bytes(index_ref.artifact_id)
        self._index = MemoryIndex.model_validate(json.loads(raw))

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
