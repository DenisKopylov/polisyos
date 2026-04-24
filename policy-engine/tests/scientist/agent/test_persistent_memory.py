"""Tests for CAS-backed persistent agent memory."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.agent.persistent_memory import (
    MemoryEntry,
    MemoryIndex,
    MemoryKind,
    MemoryQuery,
    PersistentMemoryStore,
    _keyword_score,
    _tokenize,
)

_FAKE_SHA = "sha256:" + "ab" * 32
_COUNTER = 0


def _make_store():
    """Build a mock ArtifactStore that round-trips JSON."""
    store = MagicMock()
    _blobs: dict[str, bytes] = {}

    def _put_json(obj, opts, canon_spec=None):
        global _COUNTER
        _COUNTER += 1
        aid = f"sha256:{_COUNTER:064x}"
        _blobs[aid] = json.dumps(obj, default=str).encode()
        return ArtifactRef(artifact_id=aid, kind=opts.kind, media_type="application/json")

    def _get_bytes(aid):
        # ArtifactID may be a Pydantic RootModel; convert to str for dict lookup
        return _blobs[str(aid)]

    store.put_json.side_effect = _put_json
    store.get_bytes.side_effect = _get_bytes
    return store


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestMemoryEntryModel:
    def test_defaults(self) -> None:
        e = MemoryEntry(
            kind=MemoryKind.EPISODIC,
            content="GDP growth elasticity is ~0.3",
            source_run_id="r1",
        )
        assert e.schema_version == "1.0"
        assert len(e.memory_id) == 32  # hex UUID
        assert e.confidence == 1.0
        assert e.expires_at is None

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="x",
                source_run_id="r1",
                bad="field",
            )

    def test_roundtrip(self) -> None:
        e = MemoryEntry(
            kind=MemoryKind.SEMANTIC,
            content="minimum wage has negative employment effect",
            tags=["labor", "economics"],
            source_run_id="r2",
            confidence=0.85,
        )
        dumped = e.model_dump(mode="json")
        restored = MemoryEntry.model_validate(dumped)
        assert restored.kind == MemoryKind.SEMANTIC
        assert restored.confidence == 0.85
        assert restored.tags == ["labor", "economics"]


class TestMemoryIndexModel:
    def test_defaults(self) -> None:
        idx = MemoryIndex()
        assert idx.schema_version == "1.0"
        assert idx.entries == []

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            MemoryIndex(bad="field")


class TestMemoryQueryModel:
    def test_defaults(self) -> None:
        q = MemoryQuery()
        assert q.query_text is None
        assert q.max_results == 10
        assert q.min_confidence == 0.0

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            MemoryQuery(bad="field")


# ---------------------------------------------------------------------------
# Tokenization and scoring
# ---------------------------------------------------------------------------


class TestKeywordScoring:
    def test_tokenize(self) -> None:
        tokens = _tokenize("GDP per capita growth")
        assert "gdp" in tokens
        assert "per" in tokens
        assert "capita" in tokens

    def test_short_words_excluded(self) -> None:
        tokens = _tokenize("a is to the GDP")
        assert "a" not in tokens
        assert "is" not in tokens
        assert "to" not in tokens
        assert "the" in tokens  # 3 chars → included
        assert "gdp" in tokens

    def test_perfect_overlap(self) -> None:
        query_tokens = _tokenize("GDP growth")
        score = _keyword_score(query_tokens, "GDP growth rate")
        assert score == 1.0  # both query tokens present

    def test_partial_overlap(self) -> None:
        query_tokens = _tokenize("GDP growth rate")
        score = _keyword_score(query_tokens, "GDP employment")
        assert 0.0 < score < 1.0

    def test_no_overlap(self) -> None:
        query_tokens = _tokenize("inflation")
        score = _keyword_score(query_tokens, "employment rate")
        assert score == 0.0

    def test_empty_query(self) -> None:
        assert _keyword_score(set(), "anything") == 0.0


# ---------------------------------------------------------------------------
# Store: CRUD
# ---------------------------------------------------------------------------


class TestPersistentMemoryStoreCRUD:
    def test_store_and_query(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)

        entry = MemoryEntry(
            kind=MemoryKind.EPISODIC,
            content="Minimum wage elasticity is -0.15",
            tags=["labor", "wage"],
            source_run_id="r1",
        )
        ref = mem.store_memory(entry)
        assert ref.artifact_id

        results = mem.query(MemoryQuery(query_text="wage elasticity"))
        assert len(results) == 1
        assert results[0].content == entry.content

    def test_empty_query_returns_all(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        for i in range(3):
            mem.store_memory(
                MemoryEntry(
                    kind=MemoryKind.EPISODIC,
                    content=f"fact number {i}",
                    source_run_id="r1",
                )
            )
        results = mem.query(MemoryQuery())
        assert len(results) == 3

    def test_kind_filter(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="episodic fact",
                source_run_id="r1",
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content="semantic fact",
                source_run_id="r1",
            )
        )
        results = mem.query(MemoryQuery(kind=MemoryKind.SEMANTIC))
        assert len(results) == 1
        assert results[0].kind == MemoryKind.SEMANTIC

    def test_tag_filter(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="tagged fact",
                tags=["labor", "wage"],
                source_run_id="r1",
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="other fact",
                tags=["fiscal"],
                source_run_id="r1",
            )
        )
        results = mem.query(MemoryQuery(tags=["labor"]))
        assert len(results) == 1
        assert "labor" in results[0].tags

    def test_confidence_filter(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="low conf",
                confidence=0.3,
                source_run_id="r1",
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="high conf",
                confidence=0.9,
                source_run_id="r1",
            )
        )
        results = mem.query(MemoryQuery(min_confidence=0.5))
        assert len(results) == 1
        assert results[0].confidence == 0.9

    def test_max_results(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        for i in range(10):
            mem.store_memory(
                MemoryEntry(
                    kind=MemoryKind.EPISODIC,
                    content=f"fact {i}",
                    source_run_id="r1",
                )
            )
        results = mem.query(MemoryQuery(max_results=3))
        assert len(results) == 3

    def test_ttl_expiration(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="expired",
                source_run_id="r1",
                expires_at=past,
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="valid",
                source_run_id="r1",
                expires_at=future,
            )
        )
        results = mem.query(MemoryQuery())
        assert len(results) == 1
        assert results[0].content == "valid"

    def test_keyword_relevance_ranking(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content="fiscal policy deficit spending",
                source_run_id="r1",
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content="labor market wage elasticity employment",
                source_run_id="r1",
            )
        )
        results = mem.query(MemoryQuery(query_text="wage elasticity"))
        assert len(results) == 2
        assert "wage" in results[0].content

    def test_query_filters_ttl_and_confidence_from_index_before_extra_cas_reads(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        now = datetime.now(UTC)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="expired memory",
                source_run_id="r1",
                confidence=0.9,
                expires_at=now - timedelta(hours=1),
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="low confidence memory",
                source_run_id="r1",
                confidence=0.2,
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="usable memory",
                source_run_id="r1",
                confidence=0.8,
                expires_at=now + timedelta(hours=1),
            )
        )

        store.get_bytes.reset_mock()
        results = mem.query(MemoryQuery(min_confidence=0.5, max_results=1))

        assert len(results) == 1
        assert results[0].content == "usable memory"
        assert store.get_bytes.call_count == 1

    def test_prune_expired_uses_index_metadata_without_loading_payloads(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        now = datetime.now(UTC)
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="expired memory",
                source_run_id="r1",
                expires_at=now - timedelta(hours=1),
            )
        )
        mem.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="fresh memory",
                source_run_id="r1",
                expires_at=now + timedelta(hours=1),
            )
        )

        store.get_bytes.reset_mock()
        removed = mem.prune_expired()

        assert removed == 1
        assert len(mem.index.entries) == 1
        assert store.get_bytes.call_count == 0


# ---------------------------------------------------------------------------
# Index persistence
# ---------------------------------------------------------------------------


class TestIndexPersistence:
    def test_save_and_load_index(self) -> None:
        store = _make_store()
        mem1 = PersistentMemoryStore(store)
        mem1.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="persisted fact",
                source_run_id="r1",
            )
        )
        idx_ref = mem1.save_index()

        # New store instance loads the index
        mem2 = PersistentMemoryStore(store)
        mem2.load_index(idx_ref)
        assert len(mem2.index.entries) == 1
        assert mem2.index.entries[0].content_preview == "persisted fact"

    def test_cross_run_memory(self) -> None:
        """Simulate two workflow runs sharing memory via index ref."""
        store = _make_store()

        # Run 1: remember
        mem1 = PersistentMemoryStore(store)
        mem1.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content="GDP elasticity is approximately 0.3",
                tags=["economics"],
                source_run_id="run_1",
            )
        )
        idx_ref = mem1.save_index()

        # Run 2: recall
        mem2 = PersistentMemoryStore(store)
        mem2.load_index(idx_ref)
        results = mem2.query(MemoryQuery(query_text="GDP elasticity"))
        assert len(results) == 1
        assert results[0].source_run_id == "run_1"

        # Run 2 also adds memory
        mem2.store_memory(
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="New finding from run 2",
                source_run_id="run_2",
            )
        )
        idx_ref_2 = mem2.save_index()

        # Run 3: sees both
        mem3 = PersistentMemoryStore(store)
        mem3.load_index(idx_ref_2)
        assert len(mem3.index.entries) == 2

    def test_long_content_dedup_survives_save_and_load(self) -> None:
        store = _make_store()
        content = "A" * 260 + " unique suffix"

        mem1 = PersistentMemoryStore(store)
        ref1 = mem1.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content=content,
                source_run_id="run_1",
            )
        )
        ref2 = mem1.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content=content,
                source_run_id="run_1",
            )
        )
        idx_ref = mem1.save_index()

        mem2 = PersistentMemoryStore(store)
        mem2.load_index(idx_ref)
        ref3 = mem2.store_memory(
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content=content,
                source_run_id="run_2",
            )
        )

        assert str(ref1.artifact_id) == str(ref2.artifact_id)
        assert str(ref1.artifact_id) == str(ref3.artifact_id)
        assert len(mem2.index.entries) == 1
        assert mem2.index.entries[0].full_content_hash


# ---------------------------------------------------------------------------
# Format for prompt
# ---------------------------------------------------------------------------


class TestFormatForPrompt:
    def test_empty(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        assert mem.format_for_prompt([]) == ""

    def test_basic_format(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        entries = [
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="GDP growth is strong",
                tags=["economics"],
                source_run_id="r1",
            ),
            MemoryEntry(
                kind=MemoryKind.SEMANTIC,
                content="Inflation is rising",
                source_run_id="r1",
            ),
        ]
        text = mem.format_for_prompt(entries)
        assert "# PRIOR KNOWLEDGE" in text
        assert "[episodic]" in text
        assert "[economics]" in text
        assert "GDP growth is strong" in text
        assert "[semantic]" in text
        assert "Inflation is rising" in text

    def test_max_chars_truncation(self) -> None:
        store = _make_store()
        mem = PersistentMemoryStore(store)
        entries = [
            MemoryEntry(
                kind=MemoryKind.EPISODIC,
                content="A" * 500,
                source_run_id="r1",
            )
            for _ in range(20)
        ]
        text = mem.format_for_prompt(entries, max_chars=200)
        assert len(text) <= 600  # header + at most a few entries


# ---------------------------------------------------------------------------
# KnowledgeToolkit integration
# ---------------------------------------------------------------------------


class TestKnowledgeToolkitMemory:
    def test_remember_and_recall(self) -> None:
        from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

        store = _make_store()
        mem = PersistentMemoryStore(store)
        toolkit = KnowledgeToolkit(persistent_memory=mem)

        result = toolkit.remember(
            "Minimum wage elasticity -0.15",
            tags=["labor"],
            source_run_id="r1",
        )
        assert "memory_id" in result
        assert "artifact_id" in result

        recalled = toolkit.recall("wage elasticity")
        assert len(recalled) == 1
        assert recalled[0]["content"] == "Minimum wage elasticity -0.15"
        assert recalled[0]["tags"] == ["labor"]

    def test_remember_without_memory_returns_error(self) -> None:
        from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

        toolkit = KnowledgeToolkit()
        result = toolkit.remember("something", source_run_id="r1")
        assert "error" in result

    def test_recall_without_memory_returns_empty(self) -> None:
        from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

        toolkit = KnowledgeToolkit()
        assert toolkit.recall("anything") == []

    def test_has_persistent_memory_flag(self) -> None:
        from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

        assert not KnowledgeToolkit().has_persistent_memory
        store = _make_store()
        mem = PersistentMemoryStore(store)
        assert KnowledgeToolkit(persistent_memory=mem).has_persistent_memory


# ---------------------------------------------------------------------------
# ExperimentState schema update
# ---------------------------------------------------------------------------


class TestStateSchemaUpdate:
    def test_memory_index_ref_field(self) -> None:
        from polisyos.scientist.engine.state import ExperimentState

        state = ExperimentState(run_id="r1")
        assert state.memory_index_ref is None
        assert state.schema_version == "1.3"

    def test_memory_index_ref_roundtrip(self) -> None:
        from polisyos.scientist.engine.state import ExperimentState

        ref = ArtifactRef(artifact_id=_FAKE_SHA, kind="test", media_type="application/json")
        state = ExperimentState(run_id="r1", memory_index_ref=ref)
        dumped = state.model_dump()
        restored = ExperimentState.model_validate(dumped)
        assert restored.memory_index_ref is not None
        assert str(restored.memory_index_ref.artifact_id) == _FAKE_SHA


# ---------------------------------------------------------------------------
# ExecutionContext updates
# ---------------------------------------------------------------------------


class TestContextUpdates:
    def test_depth_field(self) -> None:
        from polisyos.scientist.engine.context import ExecutionContext

        ctx = ExecutionContext(
            store=MagicMock(),
            run=MagicMock(),
            logger=MagicMock(),
            depth=2,
        )
        assert ctx.depth == 2

    def test_memory_field(self) -> None:
        from polisyos.scientist.engine.context import ExecutionContext

        mem = MagicMock()
        ctx = ExecutionContext(
            store=MagicMock(),
            run=MagicMock(),
            logger=MagicMock(),
            memory=mem,
        )
        assert ctx.memory is mem

    def test_defaults(self) -> None:
        from polisyos.scientist.engine.context import ExecutionContext

        ctx = ExecutionContext(
            store=MagicMock(),
            run=MagicMock(),
            logger=MagicMock(),
        )
        assert ctx.depth == 0
        assert ctx.memory is None
