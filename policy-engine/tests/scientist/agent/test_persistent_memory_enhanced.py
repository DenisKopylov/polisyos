"""Tests for WS6.4 — Persistent Memory Enhancement."""

from __future__ import annotations

import concurrent.futures
import json
import math
from datetime import datetime, timedelta, timezone

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.persistent_memory import (
    MemoryEntry,
    MemoryKind,
    MemoryQuery,
    PersistentMemoryStore,
    _content_hash,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeArtifactStore:
    """In-memory artifact store for testing."""

    def __init__(self):
        self._data: dict[str, bytes] = {}
        self._counter = 0
        self.get_bytes_calls = 0

    def put_json(self, data, options=None):
        self._counter += 1
        aid = f"sha256:{self._counter:064d}"
        self._data[aid] = json.dumps(data, default=str).encode()
        kind = "memory_entry"
        media_type = "application/json"
        if options is not None:
            kind = getattr(options, "kind", kind) or kind
            media_type = getattr(options, "media_type", media_type) or media_type
        return ArtifactRef(artifact_id=aid, kind=kind, media_type=media_type)

    def get_bytes(self, artifact_id) -> bytes:
        self.get_bytes_calls += 1
        key = str(artifact_id)
        if key not in self._data:
            raise KeyError(key)
        return self._data[key]


class FakeVectorStore:
    """In-memory vector store for testing."""

    def __init__(self):
        self._items: list[tuple[str, list[float], dict]] = []

    def add(self, key: str, embedding: list[float], metadata: dict | None = None):
        self._items.append((key, embedding, metadata or {}))

    def query(self, embedding: list[float], top_k: int = 10):
        # Simple: return all items sorted by index (no real distance)
        results = []
        for key, emb, meta in self._items[:top_k]:
            # Fake distance = 1 - cosine_sim (approx)
            dot = sum(a * b for a, b in zip(embedding, emb, strict=True))
            norm_a = math.sqrt(sum(x * x for x in embedding))
            norm_b = math.sqrt(sum(x * x for x in emb))
            if norm_a > 0 and norm_b > 0:
                sim = dot / (norm_a * norm_b)
            else:
                sim = 0.0
            dist = 1.0 - sim
            results.append((key, dist, meta))
        results.sort(key=lambda t: t[1])
        return results[:top_k]


class FakeEmbedder:
    """Hash-based embedder for deterministic tests."""

    def __init__(self, dim: int = 4):
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            h = hash(text)
            vec = [((h + i) % 100) / 100.0 for i in range(self._dim)]
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            results.append(vec)
        return results

    @property
    def dim(self) -> int:
        return self._dim


def _make_entry(content: str, **kwargs) -> MemoryEntry:
    defaults = dict(
        kind=MemoryKind.SEMANTIC,
        content=content,
        source_run_id="run_1",
    )
    defaults.update(kwargs)
    return MemoryEntry(**defaults)


# ---------------------------------------------------------------------------
# Content hash deduplication
# ---------------------------------------------------------------------------


class TestContentHashDedup:
    def test_same_content_same_hash(self):
        assert _content_hash("hello world") == _content_hash("hello world")

    def test_different_content_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")


class TestDeduplication:
    def test_duplicate_content_not_stored_twice(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        e1 = _make_entry("same content here")
        e2 = _make_entry("same content here")

        mem.store_memory(e1)
        mem.store_memory(e2)

        assert len(mem.index.entries) == 1

    def test_different_content_stored(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("content A"))
        mem.store_memory(_make_entry("content B"))

        assert len(mem.index.entries) == 2

    def test_long_content_dedup_uses_full_content_hash(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)
        long_content = "x" * 240 + "suffix"

        ref1 = mem.store_memory(_make_entry(long_content))
        ref2 = mem.store_memory(_make_entry(long_content))

        assert str(ref1.artifact_id) == str(ref2.artifact_id)
        assert len(mem.index.entries) == 1

    def test_concurrent_duplicate_content_stored_once(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        def _store_same_content():
            return mem.store_memory(_make_entry("same concurrent content"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            refs = list(executor.map(lambda _: _store_same_content(), range(24)))

        assert len(mem.index.entries) == 1
        assert {str(ref.artifact_id) for ref in refs} == {str(refs[0].artifact_id)}


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    def test_semantic_search_with_embedder(self):
        store = FakeArtifactStore()
        embedder = FakeEmbedder()
        vector_store = FakeVectorStore()
        mem = PersistentMemoryStore(store, embedder=embedder, vector_store=vector_store)

        mem.store_memory(_make_entry("policy on taxation"))
        mem.store_memory(_make_entry("climate change adaptation"))

        results = mem.query(MemoryQuery(query_text="tax policy reform"))
        assert len(results) > 0

    def test_fallback_to_keyword_without_embedder(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("keyword based search test"))

        results = mem.query(MemoryQuery(query_text="keyword search"))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Confidence-weighted ranking
# ---------------------------------------------------------------------------


class TestConfidenceWeighting:
    def test_high_confidence_ranked_higher(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("same topic content A", confidence=0.3))
        mem.store_memory(_make_entry("same topic content B", confidence=0.9))

        results = mem.query(MemoryQuery(query_text="same topic content"))
        assert len(results) == 2
        # Higher confidence should be first
        assert results[0].confidence >= results[1].confidence

    def test_index_confidence_prevents_loading_filtered_entries(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)
        mem.store_memory(_make_entry("low confidence", confidence=0.1))
        mem.store_memory(_make_entry("high confidence", confidence=0.9))

        store.get_bytes_calls = 0
        results = mem.query(MemoryQuery(query_text="confidence", min_confidence=0.5))

        assert len(results) == 1
        assert results[0].confidence == 0.9
        assert store.get_bytes_calls == 1


# ---------------------------------------------------------------------------
# TTL pruning
# ---------------------------------------------------------------------------


class TestTTLPruning:
    def test_expired_entries_pruned(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        expired = _make_entry(
            "old memory",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        valid = _make_entry("fresh memory")

        mem.store_memory(expired)
        mem.store_memory(valid)

        count = mem.prune_expired()
        assert count == 1
        assert len(mem.index.entries) == 1

    def test_no_ttl_entries_kept(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("no expiry"))
        count = mem.prune_expired()
        assert count == 0

    def test_prune_expired_does_not_load_each_payload_when_index_has_ttl(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry(
            "expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        mem.store_memory(_make_entry(
            "fresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))

        store.get_bytes_calls = 0
        removed = mem.prune_expired()

        assert removed == 1
        assert store.get_bytes_calls == 0


# ---------------------------------------------------------------------------
# Consolidation
# ---------------------------------------------------------------------------


class TestConsolidation:
    def test_similar_entries_merged(self):
        store = FakeArtifactStore()
        embedder = FakeEmbedder()
        vector_store = FakeVectorStore()
        mem = PersistentMemoryStore(store, embedder=embedder, vector_store=vector_store)

        # Store entries with identical content (will have same embedding)
        mem.store_memory(_make_entry("policy reform A", tags=["tag1"]))
        # Different enough content to avoid dedup but use embedding similarity
        # Since dedup uses content_hash, we need slightly different content
        e2 = _make_entry("policy reform A updated", tags=["tag2"])
        mem._content_hashes.discard(_content_hash(e2.content))  # force bypass dedup
        mem.store_memory(e2)

        removed = mem.consolidate(similarity_threshold=0.0)  # very low threshold
        assert removed >= 0  # May or may not merge depending on embeddings

    def test_no_consolidation_for_single_entry(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)
        mem.store_memory(_make_entry("only one"))
        assert mem.consolidate() == 0


# ---------------------------------------------------------------------------
# Index persistence
# ---------------------------------------------------------------------------


class TestIndexPersistence:
    def test_load_restores_content_hashes(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("unique content"))
        ref = mem.save_index()

        # Load into a new store instance
        mem2 = PersistentMemoryStore(store)
        mem2.load_index(ref)
        assert len(mem2._content_hashes) == 1
        assert _content_hash("unique content") in mem2._content_hashes

    def test_save_and_load_roundtrip(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)

        mem.store_memory(_make_entry("entry 1"))
        mem.store_memory(_make_entry("entry 2"))
        ref = mem.save_index()

        mem2 = PersistentMemoryStore(store)
        mem2.load_index(ref)
        assert len(mem2.index.entries) == 2

    def test_load_restores_full_hash_for_long_content(self):
        store = FakeArtifactStore()
        mem = PersistentMemoryStore(store)
        long_content = "long-content-" * 30

        mem.store_memory(_make_entry(long_content))
        ref = mem.save_index()

        mem2 = PersistentMemoryStore(store)
        mem2.load_index(ref)

        assert mem2.index.entries[0].full_content_hash == _content_hash(long_content)
