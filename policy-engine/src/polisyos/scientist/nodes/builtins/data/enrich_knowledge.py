"""Public data enrich knowledge module API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scholar import (
    FreshnessStatus,
    KnowledgeBundleRef,
    ResearchIntent,
    ResearchIntentRef,
)
from polisyos.scholar.freshness import (
    FreshnessPolicy,
    build_freshness_metadata,
    timed_freshness_check,
)
from polisyos.scholar.freshness_store import FreshnessStateStore
from polisyos.scholar.types import KnowledgeBundlePayloadV1
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.idempotency import NodeResultCache, compute_idempotency_key
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_enrich_knowledge@1.1.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Enrich Knowledge",
    description="Build knowledge_bundle_ref from research_intent_ref via Scholar.",
    tags=["builtin", "scholar"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_KNOWLEDGE_BUNDLE_REF}",
        f"inputs.{INPUT_RESEARCH_INTENT_REF}",
    ],
    state_writes=[f"inputs.{INPUT_KNOWLEDGE_BUNDLE_REF}"],
    produces=[INPUT_KNOWLEDGE_BUNDLE_REF],
)


@dataclass(frozen=True)
class EnrichKnowledgeNode:
    """Data-stage DAG node that refreshes or reuses the knowledge bundle for a research intent.

    Requires `inputs.research_intent_ref` and a configured Scholar port, then
    writes `inputs.knowledge_bundle_ref` after freshness checks or a live refresh.
    """
    auto_refresh_on_stale: bool = True
    block_on_expired: bool = False
    refresh_cooldown_seconds: int = 3600

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ctx.scholar is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDATION_MISSING,
                    message="Scholar port is not configured",
                ),
            )

        intent_ref_raw = state.inputs.get(INPUT_RESEARCH_INTENT_REF)
        if intent_ref_raw is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Missing research_intent_ref",
                    details={"required": [INPUT_RESEARCH_INTENT_REF]},
                ),
            )

        try:
            intent_ref = ResearchIntentRef.model_validate(intent_ref_raw.model_dump())
            payload = from_canonical_bytes(ctx.store.get_bytes(intent_ref.artifact_id))
            if not isinstance(payload, dict):
                raise ValueError("research_intent_ref must point to JSON object payload")
            intent = ResearchIntent.model_validate(payload)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="scholar.intent_load_failed",
                    message=f"Failed to load research intent: {exc}",
                ),
            )

        freshness_store = FreshnessStateStore(ctx.store)
        existing_ref = self._resolve_existing_bundle_ref(ctx, state)
        existing_bundle: KnowledgeBundlePayloadV1 | None = None
        if existing_ref is not None:
            try:
                existing_bundle = self._load_bundle_payload(ctx, existing_ref)
            except Exception:
                existing_bundle = None

        if existing_ref is not None and existing_bundle is not None:
            policy = FreshnessPolicy(
                auto_refresh_on_stale=self.auto_refresh_on_stale,
                block_on_expired=self.block_on_expired,
                refresh_cooldown_seconds=self.refresh_cooldown_seconds,
            )
            drift_signals = self._extract_drift_signals(state)
            state_key = self._freshness_state_key(
                intent_ref=intent_ref,
                bundle_ref=str(existing_ref.artifact_id),
            )
            runtime_state = freshness_store.load(state_key)
            check_time = datetime.now(timezone.utc)
            freshness_result = timed_freshness_check(
                policy,
                bundle_ref=str(existing_ref.artifact_id),
                freshness=existing_bundle.freshness,
                runtime_state=runtime_state,
                now=check_time,
                external_drift_signals=drift_signals,
            )
            freshness_store.record_check(state_key, now=check_time)

            if (
                freshness_result.status is FreshnessStatus.EXPIRED
                and self.block_on_expired
                and freshness_result.needs_refresh
            ):
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code="scholar.bundle_expired",
                        message="Knowledge bundle expired and refresh is required",
                        details={
                            "bundle_ref": str(existing_ref.artifact_id),
                            "age_seconds": freshness_result.age_seconds,
                        },
                    ),
                )

            if not freshness_result.needs_refresh:
                return self._reuse_outcome(
                    state=state,
                    bundle_ref=existing_ref,
                    freshness=freshness_result,
                )

            lock = freshness_store.acquire_lock(
                state_key,
                ttl_seconds=max(self.refresh_cooldown_seconds, 300),
            )
            if lock is None:
                return self._reuse_outcome(
                    state=state,
                    bundle_ref=existing_ref,
                    freshness=freshness_result,
                    level="warn",
                    code="scholar.refresh_in_progress",
                    message="Another process is refreshing this bundle; reusing current bundle",
                )

            with lock:
                # Re-check after lock acquisition in case another worker refreshed recently.
                runtime_state = freshness_store.load(state_key)
                recheck_time = datetime.now(timezone.utc)
                freshness_result = timed_freshness_check(
                    policy,
                    bundle_ref=str(existing_ref.artifact_id),
                    freshness=existing_bundle.freshness,
                    runtime_state=runtime_state,
                    now=recheck_time,
                    external_drift_signals=drift_signals,
                )
                freshness_store.record_check(state_key, now=recheck_time)
                if not freshness_result.needs_refresh:
                    return self._reuse_outcome(
                        state=state,
                        bundle_ref=existing_ref,
                        freshness=freshness_result,
                    )

                refresh_time = datetime.now(timezone.utc)
                freshness_store.record_refresh_attempt(state_key, now=refresh_time)
                try:
                    refreshed_ref = ctx.scholar.enrich(ctx.store, intent)
                except Exception:
                    refreshed_state = freshness_store.record_refresh_failure(
                        state_key,
                        cooldown_seconds=self.refresh_cooldown_seconds,
                        now=refresh_time,
                    )
                    return self._reuse_outcome(
                        state=state,
                        bundle_ref=existing_ref,
                        freshness=FreshnessPolicy(
                            auto_refresh_on_stale=self.auto_refresh_on_stale,
                            block_on_expired=self.block_on_expired,
                            refresh_cooldown_seconds=self.refresh_cooldown_seconds,
                        ).check(
                            bundle_ref=str(existing_ref.artifact_id),
                            freshness=existing_bundle.freshness,
                            runtime_state=refreshed_state,
                            now=refresh_time,
                            external_drift_signals=drift_signals,
                        ),
                        level="warn",
                        code="scholar.refresh_failed_stale_reused",
                        message="Refresh failed; reusing stale knowledge bundle",
                    )

                freshness_store.record_refresh_success(state_key, now=datetime.now(timezone.utc))
                finalized_ref = self._finalize_refreshed_bundle(
                    ctx=ctx,
                    intent=intent,
                    refreshed_ref=refreshed_ref,
                    previous_ref=existing_ref,
                    previous_bundle=existing_bundle,
                )
                return self._success_outcome(state, finalized_ref)

        try:
            refreshed_ref = ctx.scholar.enrich(ctx.store, intent)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="scholar.enrich_failed",
                    message=f"Scholar enrich failed: {exc}",
                ),
            )
        return self._success_outcome(state, refreshed_ref)

    def _success_outcome(
        self,
        state: ExperimentState,
        bundle_ref: KnowledgeBundleRef,
    ) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = bundle_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref],
            events=[
                NodeEvent(
                    level="info",
                    code="scholar.bundle_enriched",
                    message="Knowledge bundle enriched",
                )
            ],
        )

    def _reuse_outcome(
        self,
        *,
        state: ExperimentState,
        bundle_ref: KnowledgeBundleRef,
        freshness: Any,
        level: str | None = None,
        code: str | None = None,
        message: str | None = None,
    ) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF] = bundle_ref
        effective_level = level or ("warn" if freshness.blocked_by_cooldown else "info")
        effective_code = code or (
            "scholar.refresh_cooldown" if freshness.blocked_by_cooldown else "scholar.bundle_reused"
        )
        effective_message = message or (
            "Knowledge bundle refresh skipped due to cooldown"
            if freshness.blocked_by_cooldown
            else "Knowledge bundle reused (freshness check passed)"
        )
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref],
            events=[
                NodeEvent(
                    level=effective_level,
                    code=effective_code,
                    message=effective_message,
                    attrs={
                        "status": freshness.status.value,
                        "age_seconds": int(freshness.age_seconds),
                        "reason": freshness.reason,
                        "retry_after_seconds": freshness.retry_after_seconds,
                    },
                )
            ],
        )

    def _finalize_refreshed_bundle(
        self,
        *,
        ctx: ExecutionContext,
        intent: ResearchIntent,
        refreshed_ref: KnowledgeBundleRef,
        previous_ref: KnowledgeBundleRef,
        previous_bundle: KnowledgeBundlePayloadV1,
    ) -> KnowledgeBundleRef:
        try:
            refreshed_bundle = self._load_bundle_payload(ctx, refreshed_ref)
        except Exception:
            return refreshed_ref

        merged_freshness = build_freshness_metadata(
            domain=intent.domain,
            source_freshness_at=(
                refreshed_bundle.freshness.source_freshness_at
                or previous_bundle.freshness.source_freshness_at
            ),
            previous_bundle_ref=str(previous_ref.artifact_id),
            enrichment_count=max(
                previous_bundle.freshness.enrichment_count + 1,
                refreshed_bundle.freshness.enrichment_count,
            ),
            now=refreshed_bundle.freshness.created_at,
        )
        updated_bundle = refreshed_bundle.model_copy(update={"freshness": merged_freshness})
        return self._store_bundle_payload(ctx, updated_bundle)

    def _freshness_state_key(self, *, intent_ref: ResearchIntentRef, bundle_ref: str) -> str:
        return FreshnessStateStore.make_key(str(intent_ref.artifact_id), bundle_ref)

    def _resolve_existing_bundle_ref(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> KnowledgeBundleRef | None:
        current = state.inputs.get(INPUT_KNOWLEDGE_BUNDLE_REF)
        if current is not None:
            try:
                return KnowledgeBundleRef.model_validate(current.model_dump())
            except Exception:
                return None

        try:
            cache = NodeResultCache(ctx.store, run_id=state.run_id)
            cache.seed_from_trace(ctx.run.trace_path)
            key = compute_idempotency_key(spec=self.spec, state=state, bind_params=None)
            cached = cache.get(key)
            if cached is None:
                return None
            cached_ref = cached.state.inputs.get(INPUT_KNOWLEDGE_BUNDLE_REF)
            if cached_ref is None:
                return None
            return KnowledgeBundleRef.model_validate(cached_ref.model_dump())
        except Exception:
            return None

    def _load_bundle_payload(
        self,
        ctx: ExecutionContext,
        bundle_ref: KnowledgeBundleRef,
    ) -> KnowledgeBundlePayloadV1:
        payload = from_canonical_bytes(ctx.store.get_bytes(bundle_ref.artifact_id))
        if not isinstance(payload, dict):
            raise ValueError("knowledge_bundle_ref must point to JSON object payload")
        return KnowledgeBundlePayloadV1.model_validate(payload)

    def _store_bundle_payload(
        self,
        ctx: ExecutionContext,
        bundle: KnowledgeBundlePayloadV1,
    ) -> KnowledgeBundleRef:
        artifact = ctx.store.put_json(
            bundle.model_dump(mode="python"),
            PutOptions(
                kind="scholar.knowledge_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scholar.KnowledgeBundlePayloadV1", version="1.0"),
            ),
        )
        return KnowledgeBundleRef.model_validate(artifact.model_dump())

    def _extract_drift_signals(self, state: ExperimentState) -> dict[str, bool]:
        raw = state.params.get("scholar_drift_signals")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, bool] = {}
        for key, value in raw.items():
            if isinstance(key, str):
                result[key] = bool(value)
        return result


__all__ = ["EnrichKnowledgeNode"]
