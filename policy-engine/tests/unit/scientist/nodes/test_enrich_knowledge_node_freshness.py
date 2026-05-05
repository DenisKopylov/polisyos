from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent, ResearchIntentRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scholar.freshness import build_freshness_metadata
from polisyos.scholar.types import KnowledgeBundlePayloadV1
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)


class _FakeScholar:
    def __init__(self, *, now: datetime) -> None:
        self.calls = 0
        self._now = now

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        self.calls += 1
        payload = KnowledgeBundlePayloadV1(
            bundle_id=f"bundle.refreshed.{self.calls}",
            freshness=build_freshness_metadata(
                domain=intent.domain,
                source_freshness_at=self._now,
                now=self._now,
            ),
        )
        artifact = store.put_json(
            payload.model_dump(mode="python"),
            PutOptions(
                kind="scholar.knowledge_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scholar.KnowledgeBundlePayloadV1", version="1.0"),
            ),
        )
        return KnowledgeBundleRef.model_validate(artifact.model_dump())


class _AlwaysFailScholar:
    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        del store, intent
        self.calls += 1
        raise RuntimeError("upstream source unavailable")


class _AssertionFailScholar:
    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        del store, intent
        raise AssertionError("scholar invariant")


def _store_intent(cas: FileSystemCAS) -> ResearchIntentRef:
    intent = ResearchIntent(domain="labor")
    artifact = cas.put_json(
        intent.model_dump(mode="python"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.contracts.scholar.ResearchIntent", version="1.0"),
        ),
    )
    return ResearchIntentRef.model_validate(artifact.model_dump())


def _store_bundle(cas: FileSystemCAS, payload: KnowledgeBundlePayloadV1) -> KnowledgeBundleRef:
    artifact = cas.put_json(
        payload.model_dump(mode="python"),
        PutOptions(
            kind="scholar.knowledge_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scholar.KnowledgeBundlePayloadV1", version="1.0"),
        ),
    )
    return KnowledgeBundleRef.model_validate(artifact.model_dump())


def _build_context(tmp_path: Path, scholar: Any) -> tuple[ExecutionContext, ExperimentState]:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="R_freshness",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.enrich_knowledge"),
        scholar=scholar,
    )
    state = ExperimentState(run_id="R_freshness")
    return ctx, state


def test_enrich_node_refreshes_stale_bundle(tmp_path: Path) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    fake_scholar = _FakeScholar(now=now)
    ctx, state = _build_context(tmp_path, fake_scholar)

    intent_ref = _store_intent(ctx.store)
    stale_bundle = KnowledgeBundlePayloadV1(
        bundle_id="bundle.old",
        freshness=build_freshness_metadata(
            domain="labor",
            source_freshness_at=now - timedelta(days=60),
            now=now - timedelta(days=60),
        ).model_copy(
            update={
                "staleness_threshold_seconds": 7 * 24 * 3600,
                "expiry_threshold_seconds": 180 * 24 * 3600,
            }
        ),
    )
    stale_ref = _store_bundle(ctx.store, stale_bundle)

    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref
    state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = stale_ref

    node = EnrichKnowledgeNode(refresh_cooldown_seconds=3600)
    outcome = node.execute(ctx, state)

    assert outcome.status == "ok"
    assert fake_scholar.calls == 1
    refreshed_ref = outcome.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF]
    assert str(refreshed_ref.artifact_id) != str(stale_ref.artifact_id)


def test_enrich_node_skips_refresh_during_cooldown(tmp_path: Path) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    fake_scholar = _FakeScholar(now=now)
    ctx, state = _build_context(tmp_path, fake_scholar)

    intent_ref = _store_intent(ctx.store)
    stale_bundle = KnowledgeBundlePayloadV1(
        bundle_id="bundle.cooldown",
        freshness=build_freshness_metadata(
            domain="labor",
            source_freshness_at=now - timedelta(days=60),
            now=now - timedelta(days=60),
            last_refresh_attempt_at=now - timedelta(minutes=20),
        ).model_copy(
            update={
                "staleness_threshold_seconds": 7 * 24 * 3600,
                "expiry_threshold_seconds": 180 * 24 * 3600,
            }
        ),
    )
    stale_ref = _store_bundle(ctx.store, stale_bundle)

    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref
    state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = stale_ref

    node = EnrichKnowledgeNode(refresh_cooldown_seconds=3600)
    outcome = node.execute(ctx, state)

    assert outcome.status == "ok"
    assert fake_scholar.calls == 0
    assert str(outcome.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF].artifact_id) == str(
        stale_ref.artifact_id
    )


def test_enrich_node_failed_refresh_sets_retry_window(tmp_path: Path) -> None:
    scholar = _AlwaysFailScholar()
    ctx, state = _build_context(tmp_path, scholar)

    now = datetime.now(UTC).replace(microsecond=0)
    intent_ref = _store_intent(ctx.store)
    stale_bundle = KnowledgeBundlePayloadV1(
        bundle_id="bundle.retry-window",
        freshness=build_freshness_metadata(
            domain="labor",
            source_freshness_at=now - timedelta(days=60),
            now=now - timedelta(days=60),
        ).model_copy(
            update={
                "staleness_threshold_seconds": 7 * 24 * 3600,
                "expiry_threshold_seconds": 180 * 24 * 3600,
            }
        ),
    )
    stale_ref = _store_bundle(ctx.store, stale_bundle)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref
    state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = stale_ref

    node = EnrichKnowledgeNode(refresh_cooldown_seconds=3600)
    first = node.execute(ctx, state)
    second = node.execute(ctx, first.state)

    assert first.status == "ok"
    assert second.status == "ok"
    assert scholar.calls == 1
    assert str(second.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF].artifact_id) == str(
        stale_ref.artifact_id
    )


def test_enrich_node_scholar_assertion_is_not_swallowed(tmp_path: Path) -> None:
    ctx, state = _build_context(tmp_path, _AssertionFailScholar())
    state.inputs[INPUT_RESEARCH_INTENT_REF] = _store_intent(ctx.store)

    with pytest.raises(AssertionError, match="scholar invariant"):
        EnrichKnowledgeNode().execute(ctx, state)
