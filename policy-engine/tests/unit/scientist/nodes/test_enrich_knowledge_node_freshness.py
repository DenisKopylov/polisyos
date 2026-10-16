from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    load_core_json_artifact,
)
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonViolation
from polisyos.core.contracts.scholar import (
    KnowledgeBundleRef,
    ResearchIntent,
    ResearchIntentRef,
    SourceSpec,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.fabric.claims.persist import load_doc_meta
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.scholar import persist_knowledge_bundle_payload
from polisyos.scholar.api import ScholarService
from polisyos.scholar.freshness import build_freshness_metadata
from polisyos.scholar.freshness_store import FreshnessStateStore
from polisyos.scholar.orchestrator.bundle import persist_bundle_and_event
from polisyos.scholar.types import EnrichmentReportV1, KnowledgeBundlePayloadV1
from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


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


class _RootClaimingCachingStore(CachingArtifactStore):
    def __init__(self, *, remote: FileSystemCAS, root_value: object) -> None:
        super().__init__(remote=remote, local=remote, write_through=False)
        self._root_value = root_value
        self.root_reads = 0

    @property
    def root(self) -> object:
        self.root_reads += 1
        return self._root_value


class _FailingRootCachingStore(CachingArtifactStore):
    def __init__(self, *, remote: FileSystemCAS) -> None:
        super().__init__(remote=remote, local=remote, write_through=False)
        self.root_reads = 0

    @property
    def root(self) -> Path:
        self.root_reads += 1
        raise OSError("configured freshness root is unavailable")


class _FiniteFloatScholar:
    def __init__(self, *, now: datetime) -> None:
        self.calls = 0
        self._now = now

    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:
        self.calls += 1
        payload = KnowledgeBundlePayloadV1(
            bundle_id=f"bundle.finite-float.{self.calls}",
            web_evidence={"scores": {"estimate": 0.875, "explicit_zero": 0.0}},
            freshness=build_freshness_metadata(
                domain=intent.domain,
                source_freshness_at=self._now,
                now=self._now,
            ),
        )
        return persist_knowledge_bundle_payload(
            cas=store,
            bundle_payload=payload,
            return_selected_profile=True,
        )


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


def _store_intent(
    cas: FileSystemCAS,
    intent: ResearchIntent | None = None,
) -> ResearchIntentRef:
    intent = intent or ResearchIntent(domain="labor")
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
    assert refreshed_ref.manifest_profile_sha256 is not None
    reopened = FileSystemCAS(ctx.store.root)
    assert (
        artifact_manifest_profile_sha256(reopened.get_manifest(refreshed_ref))
        == refreshed_ref.manifest_profile_sha256
    )


def test_real_scholar_producer_returns_selected_bundle_profile(tmp_path: Path) -> None:
    declared_license = "LicenseRef-E02-CandidateFixture"
    intent = ResearchIntent(
        domain="labor",
        topic="E02 profile lineage witness",
        seed_sources=[
            SourceSpec(
                kind="bytes",
                data=b"A policy note about labor-market training and employment outcomes.",
                source_locator="e02:test:knowledge-bundle-profile",
                license=declared_license,
                mime_hint="text/plain",
            )
        ],
    )
    scholar = ScholarService(fact_log_root=tmp_path / "world-facts")
    ctx, state = _build_context(tmp_path, scholar)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = _store_intent(ctx.store, intent)

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "ok"
    bundle_ref = outcome.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF]
    assert bundle_ref.manifest_profile_sha256 is not None
    reopened = FileSystemCAS(ctx.store.root)
    manifest = reopened.get_manifest(bundle_ref)
    assert manifest.kind == "scholar.knowledge_bundle"
    assert artifact_manifest_profile_sha256(manifest) == bundle_ref.manifest_profile_sha256
    payload = load_core_json_artifact(reopened, bundle_ref)
    assert isinstance(payload, dict)
    bundle = KnowledgeBundlePayloadV1.model_validate(payload)
    source_metas = [
        load_doc_meta(reopened, str(artifact_id)) for artifact_id in bundle.doc_meta_artifact_ids
    ]
    assert any(meta.license == declared_license for meta in source_metas)


def test_bundle_writer_profile_selection_is_opt_in(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload = KnowledgeBundlePayloadV1(bundle_id="bundle.profile-opt-in")
    report = EnrichmentReportV1(bundle_artifact_id="", bundle_id=payload.bundle_id)

    default_ref, _, _ = persist_bundle_and_event(
        cas=store,
        fact_log_root=tmp_path / "default-facts",
        bundle_payload=payload,
        report_payload=report,
        doc_version_ids=[],
        claim_ids=[],
        conflict_set_ids=[],
        input_artifact_ids=[],
        persist_report=False,
    )
    selected_ref, _, _ = persist_bundle_and_event(
        cas=store,
        fact_log_root=tmp_path / "selected-facts",
        bundle_payload=payload,
        report_payload=report,
        doc_version_ids=[],
        claim_ids=[],
        conflict_set_ids=[],
        input_artifact_ids=[],
        persist_report=False,
        return_selected_profile=True,
    )

    assert default_ref.manifest_profile_sha256 is None
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    reopened = FileSystemCAS(store.root)
    manifest = reopened.get_manifest(selected_ref)
    assert artifact_manifest_profile_sha256(manifest) == selected_ref.manifest_profile_sha256


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


def test_enrich_node_repersists_finite_float_bundle_with_shared_profile(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    scholar = _FiniteFloatScholar(now=now)
    ctx, state = _build_context(tmp_path, scholar)
    intent_ref = _store_intent(
        ctx.store,
        ResearchIntent(domain="labor", topic="finite-float bundle profile"),
    )
    stale_bundle = KnowledgeBundlePayloadV1(
        bundle_id="bundle.predecessor",
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

    outcome = EnrichKnowledgeNode(refresh_cooldown_seconds=3600).execute(ctx, state)

    assert outcome.status == "ok"
    assert scholar.calls == 1
    bundle_ref = outcome.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF]
    assert isinstance(bundle_ref, KnowledgeBundleRef)
    assert bundle_ref.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(ctx.store.root)
    manifest = fresh.get_manifest(bundle_ref)
    assert manifest.kind == "scholar.knowledge_bundle"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema.name == "polisyos.scholar.KnowledgeBundlePayloadV1"
    assert manifest.artifact_schema.version == "1.0"
    assert manifest.canon is not None and manifest.canon.forbid_floats is False
    assert artifact_manifest_profile_sha256(manifest) == bundle_ref.manifest_profile_sha256
    payload = load_core_json_artifact(fresh, bundle_ref)
    assert isinstance(payload, dict)
    loaded = KnowledgeBundlePayloadV1.model_validate(payload)
    assert loaded.web_evidence["scores"] == {"estimate": 0.875, "explicit_zero": 0.0}


def test_shared_bundle_writer_keeps_missing_values_and_rejects_nonfinite_float(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_knowledge_bundle_payload(
        cas=store,
        bundle_payload=KnowledgeBundlePayloadV1(bundle_id="bundle.no-web-evidence"),
        return_selected_profile=True,
    )
    persisted = load_core_json_artifact(FileSystemCAS(store.root), ref)
    assert isinstance(persisted, dict)
    assert persisted["web_evidence"] == {}
    known_artifacts = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    invalid = KnowledgeBundlePayloadV1(
        bundle_id="bundle.nonfinite",
        web_evidence={"score": float("nan")},
    )
    with pytest.raises(CanonViolation):
        persist_knowledge_bundle_payload(
            cas=store,
            bundle_payload=invalid,
            return_selected_profile=True,
        )
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == known_artifacts


def test_enrich_node_fails_closed_when_store_has_no_root_for_freshness_state(
    tmp_path: Path,
) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    intent_ref = _store_intent(ctx.store)
    rooted_store = ctx.store
    rootless_store = CachingArtifactStore(
        remote=rooted_store,
        local=rooted_store,
        write_through=False,
    )
    assert not hasattr(rootless_store, "root")
    ctx = replace(ctx, store=rootless_store)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "scholar.freshness_state_requires_rooted_store"
    assert outcome.error.details == {"required_store_capability": "RootedArtifactStore"}
    assert scholar.calls == 0
    assert not (rooted_store.root / "freshness_state").exists()


@pytest.mark.parametrize(
    ("invalid_root", "observed_type"),
    [
        ("wrong-root", "str"),
        (17, "int"),
        (None, "NoneType"),
    ],
    ids=("string-root", "integer-root", "none-root"),
)
def test_enrich_node_refuses_invalid_root_value_before_freshness_side_effect(
    tmp_path: Path, invalid_root: object, observed_type: str
) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    claimed_path = tmp_path / "claimed-root"
    root_value = str(claimed_path) if invalid_root == "wrong-root" else invalid_root
    rooted_claim = _RootClaimingCachingStore(remote=cas, root_value=root_value)
    ctx = replace(ctx, store=rooted_claim)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "scholar.freshness_root_invalid"
    assert outcome.error.details == {
        "required_root_type": "Path",
        "observed_root_type": observed_type,
    }
    assert scholar.calls == 0
    assert rooted_claim.root_reads == 1
    assert not (cas.root / "freshness_state").exists()
    assert not claimed_path.exists()


def test_enrich_node_uses_the_single_validated_path_for_freshness_sidecar(
    tmp_path: Path,
) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    expected_root = tmp_path / "selected-sidecar-root"
    rooted_claim = _RootClaimingCachingStore(remote=cas, root_value=expected_root)
    ctx = replace(ctx, store=rooted_claim)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert rooted_claim.root_reads == 1
    assert (expected_root / "freshness_state" / "states").is_dir()
    assert (expected_root / "freshness_state" / "locks").is_dir()
    assert not (cas.root / "freshness_state").exists()


def test_enrich_node_propagates_operational_root_resolution_error(
    tmp_path: Path,
) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    failing_root = _FailingRootCachingStore(remote=cas)
    ctx = replace(ctx, store=failing_root)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    with pytest.raises(OSError, match="configured freshness root is unavailable"):
        EnrichKnowledgeNode().execute(ctx, state)

    assert failing_root.root_reads == 1
    assert scholar.calls == 0
    assert not (cas.root / "freshness_state").exists()


def test_enrich_node_refuses_missing_root_through_guarded_store(tmp_path: Path) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    rootless_store = CachingArtifactStore(
        remote=cas,
        local=cas,
        write_through=False,
    )
    guarded_store = guard_runtime_cas(rootless_store)
    ctx = replace(ctx, store=guarded_store)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "scholar.freshness_state_requires_rooted_store"
    assert outcome.error.details == {"required_store_capability": "RootedArtifactStore"}
    assert scholar.calls == 0
    assert not (cas.root / "freshness_state").exists()


@pytest.mark.parametrize(
    ("invalid_root", "observed_type"),
    [
        ("wrong-root", "str"),
        (17, "int"),
        (None, "NoneType"),
    ],
    ids=("string-root", "integer-root", "none-root"),
)
def test_enrich_node_refuses_invalid_root_through_guarded_store(
    tmp_path: Path, invalid_root: object, observed_type: str
) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    claimed_path = tmp_path / "guarded-claimed-root"
    root_value = str(claimed_path) if invalid_root == "wrong-root" else invalid_root
    rooted_claim = _RootClaimingCachingStore(remote=cas, root_value=root_value)
    guarded_store = guard_runtime_cas(rooted_claim)
    ctx = replace(ctx, store=guarded_store)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    outcome = EnrichKnowledgeNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "scholar.freshness_root_invalid"
    assert outcome.error.details == {
        "required_root_type": "Path",
        "observed_root_type": observed_type,
    }
    assert rooted_claim.root_reads == 1
    assert scholar.calls == 0
    assert not (cas.root / "freshness_state").exists()
    assert not claimed_path.exists()


def test_enrich_node_propagates_guarded_root_resolution_error(tmp_path: Path) -> None:
    scholar = _FakeScholar(now=datetime.now(UTC).replace(microsecond=0))
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    failing_root = _FailingRootCachingStore(remote=cas)
    guarded_store = guard_runtime_cas(failing_root)
    ctx = replace(ctx, store=guarded_store)
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref

    with pytest.raises(OSError, match="configured freshness root is unavailable"):
        EnrichKnowledgeNode().execute(ctx, state)

    assert failing_root.root_reads == 1
    assert scholar.calls == 0
    assert not (cas.root / "freshness_state").exists()


def test_enrich_node_reuses_guarded_cas_bundle_during_persisted_cooldown(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    scholar = _FakeScholar(now=now)
    ctx, state = _build_context(tmp_path, scholar)
    cas = ctx.store
    intent_ref = _store_intent(cas)
    stale_bundle = KnowledgeBundlePayloadV1(
        bundle_id="bundle.guarded-cooldown",
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
    stale_ref = _store_bundle(cas, stale_bundle)
    state_key = FreshnessStateStore.make_key(
        str(intent_ref.artifact_id), str(stale_ref.artifact_id)
    )
    seeded = FreshnessStateStore(cas.root).record_refresh_attempt(state_key, now=now)
    assert seeded.last_refresh_attempt_at == now
    state.inputs[INPUT_RESEARCH_INTENT_REF] = intent_ref
    state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = stale_ref
    guarded_store = guard_runtime_cas(cas)
    ctx = replace(ctx, store=guarded_store)

    outcome = EnrichKnowledgeNode(refresh_cooldown_seconds=3600).execute(ctx, state)

    assert outcome.status == "ok"
    assert outcome.error is None
    assert scholar.calls == 0
    returned_ref = outcome.state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF]
    assert str(returned_ref.artifact_id) == str(stale_ref.artifact_id)
    assert len(outcome.events) == 1
    assert outcome.events[0].code == "scholar.refresh_cooldown"
    assert outcome.events[0].attrs["status"] == "stale"
    assert outcome.events[0].attrs["reason"] == "refresh cooldown active"
    visible_root = guarded_store.root
    persisted = FreshnessStateStore(visible_root).load(state_key)
    assert persisted.last_refresh_attempt_at == now
